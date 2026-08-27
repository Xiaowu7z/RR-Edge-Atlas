package com.cfoptimizer

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.Locale
import java.util.concurrent.TimeUnit

class CloudflareDnsException(message: String) : RuntimeException(message)

data class CnameUpsertResult(
    val operation: String,
    val zoneId: String,
    val recordId: String,
    val name: String,
    val target: String,
    val proxied: Boolean
)

fun interface CloudflareTransport {
    fun request(method: String, path: String, payload: Map<String, Any?>?): Map<String, Any?>
}

/** Exact-name Cloudflare CNAME create/update with conflict protection. */
object CloudflareDns {
    private val idPattern = Regex("^[0-9a-fA-F]{32}$")

    fun upsertCname(
        apiToken: String,
        recordName: String,
        target: String,
        zoneId: String = "",
        zoneName: String = "",
        proxied: Boolean = false,
        transport: CloudflareTransport? = null
    ): CnameUpsertResult {
        val token = apiToken.trim()
        if (token.length !in 20..512 || token.any { it.isWhitespace() }) {
            throw CloudflareDnsException("API Token 格式无效")
        }
        val client = transport ?: OkHttpCloudflareTransport(token)
        val (resolvedZoneId, resolvedZoneName) = resolveZone(client, zoneId, zoneName)
        val name = normalizeRecordName(recordName, resolvedZoneName)
        val content = try { DomainSources.normalizeDomain(target) } catch (e: DomainSourceException) {
            throw CloudflareDnsException("CNAME 目标无效：${e.message}")
        }
        if (name == content) {
            throw CloudflareDnsException("记录名称与 CNAME 目标不能相同，否则会形成解析循环")
        }

        val query = "name=${encode(name)}&per_page=100"
        val response = requestChecked(client, "GET", "/zones/$resolvedZoneId/dns_records?$query", null)
        val rows = mapList(response["result"])
            ?: throw CloudflareDnsException("无法读取现有 DNS 记录")
        val exact = rows.filter {
            it["name"]?.toString()?.lowercase(Locale.ROOT)?.trimEnd('.') == name
        }
        val nonCname = exact.filter { !it["type"].toString().equals("CNAME", ignoreCase = true) }
        if (nonCname.isNotEmpty()) {
            val types = nonCname.map { it["type"]?.toString().orEmpty().ifEmpty { "?" } }.toSortedSet()
            throw CloudflareDnsException("同名记录已存在（${types.joinToString(", ")}），请先在 Cloudflare 中处理冲突")
        }
        val cnameRows = exact.filter { it["type"].toString().equals("CNAME", ignoreCase = true) }
        if (cnameRows.size > 1) {
            throw CloudflareDnsException("检测到多个同名 CNAME，已停止以避免更新错误记录")
        }

        val payload = linkedMapOf<String, Any?>(
            "type" to "CNAME",
            "name" to name,
            "content" to content,
            "ttl" to 1,
            "proxied" to proxied
        )
        if (cnameRows.isNotEmpty()) {
            val current = cnameRows.first()
            val recordId = current["id"]?.toString().orEmpty()
            if (!idPattern.matches(recordId)) {
                throw CloudflareDnsException("现有 DNS 记录 ID 无效")
            }
            val unchanged = current["content"]?.toString()?.lowercase(Locale.ROOT)?.trimEnd('.') == content &&
                (current["proxied"] as? Boolean ?: false) == proxied &&
                numberAsInt(current["ttl"], 1) == 1
            if (unchanged) {
                return CnameUpsertResult("unchanged", resolvedZoneId, recordId, name, content, proxied)
            }
            val changed = requestChecked(
                client,
                "PATCH",
                "/zones/$resolvedZoneId/dns_records/$recordId",
                payload
            )
            return changedResult("updated", resolvedZoneId, name, content, proxied, changed)
        }

        val changed = requestChecked(client, "POST", "/zones/$resolvedZoneId/dns_records", payload)
        return changedResult("created", resolvedZoneId, name, content, proxied, changed)
    }

    private fun resolveZone(
        transport: CloudflareTransport,
        zoneId: String,
        zoneName: String
    ): Pair<String, String> {
        val normalizedId = normalizeId(zoneId)
        val normalizedName = if (zoneName.isBlank()) "" else try {
            DomainSources.normalizeDomain(zoneName)
        } catch (e: DomainSourceException) {
            throw CloudflareDnsException("区域域名无效：${e.message}")
        }
        if (normalizedId.isNotEmpty()) return normalizedId to normalizedName
        if (normalizedName.isEmpty()) throw CloudflareDnsException("请填写 Zone ID 或区域域名")
        val query = "name=${encode(normalizedName)}&status=active&per_page=2"
        val response = requestChecked(transport, "GET", "/zones?$query", null)
        val rows = mapList(response["result"])
        if (rows == null || rows.size != 1) {
            throw CloudflareDnsException("未找到唯一的活动区域；请改填 Zone ID，并确认 Token 已授予 Zone Read")
        }
        val found = rows.first()
        val resolvedId = normalizeId(found["id"]?.toString().orEmpty())
        val resolvedName = try {
            DomainSources.normalizeDomain(found["name"]?.toString().orEmpty().ifEmpty { normalizedName })
        } catch (e: DomainSourceException) {
            throw CloudflareDnsException("Cloudflare 返回的区域域名无效：${e.message}")
        }
        return resolvedId to resolvedName
    }

    private fun normalizeRecordName(value: String, zoneName: String): String {
        var raw = value.trim()
        raw = when {
            raw == "@" -> zoneName.ifEmpty {
                throw CloudflareDnsException("使用 @ 时必须同时填写区域域名")
            }
            !raw.contains('.') && zoneName.isNotEmpty() -> "$raw.$zoneName"
            else -> raw
        }
        val record = try { DomainSources.normalizeDomain(raw) } catch (e: DomainSourceException) {
            throw CloudflareDnsException("记录名称无效：${e.message}")
        }
        if (zoneName.isNotEmpty() && record != zoneName && !record.endsWith(".$zoneName")) {
            throw CloudflareDnsException("CNAME 记录名称不属于所填区域")
        }
        return record
    }

    private fun normalizeId(value: String): String {
        val id = value.trim()
        if (id.isNotEmpty() && !idPattern.matches(id)) {
            throw CloudflareDnsException("Zone ID 应为 32 位十六进制字符串")
        }
        return id.lowercase(Locale.ROOT)
    }

    private fun requestChecked(
        transport: CloudflareTransport,
        method: String,
        path: String,
        payload: Map<String, Any?>?
    ): Map<String, Any?> {
        val response = transport.request(method, path, payload)
        if (response["success"] == false) throw CloudflareDnsException(apiError(response))
        return response
    }

    private fun changedResult(
        operation: String,
        zoneId: String,
        name: String,
        content: String,
        proxied: Boolean,
        response: Map<String, Any?>
    ): CnameUpsertResult {
        val result = stringMap(response["result"])
            ?: throw CloudflareDnsException("Cloudflare API 未返回 DNS 记录")
        val recordId = result["id"]?.toString().orEmpty()
        if (!idPattern.matches(recordId)) {
            throw CloudflareDnsException("Cloudflare API 返回的 DNS 记录 ID 无效")
        }
        return CnameUpsertResult(operation, zoneId, recordId, name, content, proxied)
    }

    private fun apiError(response: Map<String, Any?>, status: Int? = null): String {
        val errors = response["errors"] as? List<*> ?: emptyList<Any?>()
        val messages = errors.mapNotNull { item ->
            val row = stringMap(item) ?: return@mapNotNull null
            val message = row["message"]?.toString()?.trim().orEmpty()
            if (message.isEmpty()) null else row["code"]?.let { "$it: $message" } ?: message
        }.take(3)
        if (messages.isNotEmpty()) return messages.joinToString("；")
        return "Cloudflare API 请求失败${status?.let { "（HTTP $it）" }.orEmpty()}"
    }

    private fun encode(value: String): String =
        URLEncoder.encode(value, StandardCharsets.UTF_8.name()).replace("+", "%20")

    private fun numberAsInt(value: Any?, fallback: Int): Int = when (value) {
        is Number -> value.toInt()
        else -> value?.toString()?.toIntOrNull() ?: fallback
    }

    private fun mapList(value: Any?): List<Map<String, Any?>>? =
        (value as? List<*>)?.mapNotNull { stringMap(it) }

    private fun stringMap(value: Any?): Map<String, Any?>? {
        val raw = value as? Map<*, *> ?: return null
        return raw.entries.associate { it.key.toString() to it.value }
    }

    private class OkHttpCloudflareTransport(private val token: String) : CloudflareTransport {
        private val mediaType = "application/json; charset=utf-8".toMediaType()
        private val client = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .callTimeout(20, TimeUnit.SECONDS)
            .retryOnConnectionFailure(false)
            .build()

        override fun request(method: String, path: String, payload: Map<String, Any?>?): Map<String, Any?> {
            val builder = Request.Builder()
                .url("https://api.cloudflare.com/client/v4$path")
                .header("Authorization", "Bearer $token")
                .header("Accept", "application/json")
                .header("User-Agent", "RR-Edge-Atlas-Android/2.8.0")
            val body = SimpleJson.stringify(payload ?: emptyMap<String, Any?>()).toRequestBody(mediaType)
            when (method) {
                "GET" -> builder.get()
                "POST" -> builder.post(body)
                "PATCH" -> builder.patch(body)
                else -> throw CloudflareDnsException("不支持的 Cloudflare API 请求")
            }
            try {
                client.newCall(builder.build()).execute().use { response ->
                    val bytes = response.body?.byteStream()?.let { readLimited(it) } ?: ByteArray(0)
                    val parsed = try { stringMap(SimpleJson.parse(bytes.toString(Charsets.UTF_8))) } catch (_: Exception) { null }
                        ?: emptyMap()
                    if (!response.isSuccessful) throw CloudflareDnsException(apiError(parsed, response.code))
                    if (parsed["success"] != true) throw CloudflareDnsException(apiError(parsed))
                    return parsed
                }
            } catch (e: CloudflareDnsException) {
                throw e
            } catch (e: IOException) {
                throw CloudflareDnsException("无法连接 Cloudflare API：${e.message?.take(120) ?: e.javaClass.simpleName}")
            }
        }

        private fun readLimited(input: java.io.InputStream): ByteArray {
            input.use { stream ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(16 * 1024)
                var total = 0
                while (true) {
                    val count = stream.read(buffer)
                    if (count < 0) break
                    total += count
                    if (total > DomainSources.MAX_SOURCE_BYTES) {
                        throw CloudflareDnsException("Cloudflare API 返回内容过大")
                    }
                    output.write(buffer, 0, count)
                }
                return output.toByteArray()
            }
        }
    }
}
