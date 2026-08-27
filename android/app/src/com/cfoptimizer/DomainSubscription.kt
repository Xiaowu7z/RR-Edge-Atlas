package com.cfoptimizer

import okhttp3.Dns
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.IDN
import java.net.Inet4Address
import java.net.Inet6Address
import java.net.InetAddress
import java.net.Proxy
import java.net.URI
import java.net.UnknownHostException
import java.util.Locale
import java.util.concurrent.TimeUnit

fun interface SubscriptionResolver {
    fun resolve(hostname: String): List<InetAddress>
}

data class ValidatedSubscriptionUrl(val uri: URI, val addresses: List<InetAddress>)
data class SubscriptionImportResult(val parsed: DomainParseResult, val finalUrl: String)

/** Downloads public HTTP(S) domain subscriptions with DNS pinning and checked redirects. */
object DomainSubscription {
    private const val TIMEOUT_SECONDS = 12L
    private const val MAX_REDIRECTS = 5

    private val systemResolver = SubscriptionResolver { hostname ->
        InetAddress.getAllByName(hostname).toList()
    }

    fun validateUrl(
        value: String,
        resolver: SubscriptionResolver = systemResolver
    ): ValidatedSubscriptionUrl {
        val input = value.trim()
        val parsed = try { URI(input) } catch (_: Exception) {
            throw DomainSourceException("订阅链接格式无效")
        }
        val scheme = parsed.scheme?.lowercase(Locale.ROOT)
        if (scheme !in setOf("http", "https")) {
            throw DomainSourceException("订阅链接只支持 HTTP/HTTPS")
        }
        if (parsed.userInfo != null || parsed.rawUserInfo != null) {
            throw DomainSourceException("订阅链接不能包含账号或密码")
        }
        val rawHost = parsed.host ?: authorityHost(parsed.rawAuthority.orEmpty())
        val host = if (rawHost.contains(':')) {
            rawHost.lowercase(Locale.ROOT)
        } else try {
            IDN.toASCII(rawHost, IDN.USE_STD3_ASCII_RULES).lowercase(Locale.ROOT)
        } catch (_: Exception) {
            throw DomainSourceException("订阅链接主机名无效")
        }
        if (host.isEmpty()) throw DomainSourceException("订阅链接格式无效")
        val port = parsed.port
        if (port !in listOf(-1, 80, 443)) {
            throw DomainSourceException("订阅链接只允许 80 或 443 端口")
        }
        val normalized = try {
            val displayHost = if (host.contains(':')) "[$host]" else host
            val displayPort = if (port >= 0) ":$port" else ""
            val rawPath = parsed.rawPath?.takeIf { it.isNotEmpty() } ?: "/"
            val rawQuery = parsed.rawQuery?.let { "?$it" }.orEmpty()
            URI("$scheme://$displayHost$displayPort$rawPath$rawQuery")
        } catch (_: Exception) {
            throw DomainSourceException("订阅链接格式无效")
        }
        val addresses = try { resolver.resolve(host).distinctBy { it.hostAddress } } catch (_: Exception) {
            throw DomainSourceException("订阅域名解析失败")
        }
        if (addresses.isEmpty()) throw DomainSourceException("订阅域名没有可用地址")
        if (addresses.any { !isPublicAddress(it) }) {
            throw DomainSourceException("订阅链接不能指向本机、内网或保留地址")
        }
        return ValidatedSubscriptionUrl(normalized, addresses)
    }

    fun fetch(
        value: String,
        resolver: SubscriptionResolver = systemResolver
    ): SubscriptionImportResult {
        var current = validateUrl(value, resolver)
        repeat(MAX_REDIRECTS + 1) { redirectCount ->
            val pinnedAddresses = current.addresses
            val pinnedHost = current.uri.host
            val dns = object : Dns {
                override fun lookup(hostname: String): List<InetAddress> {
                    if (!hostname.equals(pinnedHost, ignoreCase = true)) {
                        throw UnknownHostException("未校验的订阅主机")
                    }
                    return pinnedAddresses
                }
            }
            val client = OkHttpClient.Builder()
                .dns(dns)
                .proxy(Proxy.NO_PROXY)
                .followRedirects(false)
                .followSslRedirects(false)
                .connectTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
                .readTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
                .callTimeout(TIMEOUT_SECONDS + 3, TimeUnit.SECONDS)
                .retryOnConnectionFailure(false)
                .build()
            val request = Request.Builder()
                .url(current.uri.toASCIIString())
                .header("Accept", "text/plain, application/json, text/csv, application/octet-stream")
                .header("User-Agent", "RR-Edge-Atlas-Android/2.7.1")
                .get()
                .build()
            try {
                client.newCall(request).execute().use { response ->
                    if (response.code in 300..399) {
                        if (redirectCount >= MAX_REDIRECTS) {
                            throw DomainSourceException("订阅重定向次数过多")
                        }
                        val location = response.header("Location")
                            ?: throw DomainSourceException("订阅重定向缺少目标地址")
                        val redirected = try { current.uri.resolve(location).toString() } catch (_: Exception) {
                            throw DomainSourceException("订阅重定向地址无效")
                        }
                        current = validateUrl(redirected, resolver)
                        return@use
                    }
                    if (!response.isSuccessful) {
                        throw DomainSourceException("订阅链接返回 HTTP ${response.code}")
                    }
                    val contentType = response.header("Content-Type").orEmpty()
                        .substringBefore(';').trim().lowercase(Locale.ROOT)
                    if (contentType == "text/html") {
                        throw DomainSourceException("订阅链接返回了网页，不是域名列表")
                    }
                    val contentLength = response.header("Content-Length")?.toLongOrNull()
                    if (contentLength != null && contentLength > DomainSources.MAX_SOURCE_BYTES) {
                        throw DomainSourceException("订阅内容不能超过 1 MiB")
                    }
                    val body = response.body ?: throw DomainSourceException("订阅内容为空")
                    val payload = readLimited(body.byteStream())
                    val filename = dispositionFilename(response.header("Content-Disposition"))
                        ?: current.uri.path.substringAfterLast('/').ifEmpty { "subscription" }
                    return SubscriptionImportResult(
                        parsed = DomainSources.parseBytes(payload, filename),
                        finalUrl = current.uri.toASCIIString()
                    )
                }
            } catch (e: DomainSourceException) {
                throw e
            } catch (e: IOException) {
                throw DomainSourceException("订阅下载失败：${e.message?.take(120) ?: e.javaClass.simpleName}")
            }
        }
        throw DomainSourceException("订阅重定向次数过多")
    }

    fun isPublicAddress(address: InetAddress): Boolean {
        if (address.isAnyLocalAddress || address.isLoopbackAddress || address.isLinkLocalAddress ||
            address.isSiteLocalAddress || address.isMulticastAddress) return false
        val bytes = address.address.map { it.toInt() and 0xff }
        return when (address) {
            is Inet4Address -> {
                val a = bytes[0]; val b = bytes[1]; val c = bytes[2]
                when {
                    a == 0 || a >= 224 -> false
                    a == 100 && b in 64..127 -> false
                    a == 169 && b == 254 -> false
                    a == 192 && b == 0 && c == 0 -> false
                    a == 192 && b == 0 && c == 2 -> false
                    a == 192 && b == 88 && c == 99 -> false
                    a == 198 && b in 18..19 -> false
                    a == 198 && b == 51 && c == 100 -> false
                    a == 203 && b == 0 && c == 113 -> false
                    else -> true
                }
            }
            is Inet6Address -> {
                val uniqueLocal = (bytes[0] and 0xfe) == 0xfc
                val documentation = bytes[0] == 0x20 && bytes[1] == 0x01 && bytes[2] == 0x0d && bytes[3] == 0xb8
                val orchid = bytes[0] == 0x20 && bytes[1] == 0x01 &&
                    (bytes[2] == 0x00 && (bytes[3] and 0xf0) in setOf(0x10, 0x20))
                val discardOnly = bytes.take(8) == listOf(0x01, 0x00, 0, 0, 0, 0, 0, 0)
                !uniqueLocal && !documentation && !orchid && !discardOnly
            }
            else -> false
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
                    throw DomainSourceException("订阅内容不能超过 1 MiB")
                }
                output.write(buffer, 0, count)
            }
            return output.toByteArray()
        }
    }

    private fun dispositionFilename(value: String?): String? {
        if (value.isNullOrBlank()) return null
        return Regex("filename\\s*=\\s*\"([^\"]+)\"", RegexOption.IGNORE_CASE)
            .find(value)?.groupValues?.getOrNull(1)?.substringAfterLast('/')?.substringAfterLast('\\')
    }

    private fun authorityHost(authority: String): String {
        val withoutUser = authority.substringAfterLast('@')
        if (withoutUser.startsWith('[')) return withoutUser.substringAfter('[').substringBefore(']')
        val possiblePort = withoutUser.substringAfterLast(':', "")
        return if (withoutUser.count { it == ':' } == 1 && possiblePort.all { it.isDigit() }) {
            withoutUser.substringBeforeLast(':')
        } else withoutUser
    }
}
