import com.cfoptimizer.CloudflareDns
import com.cfoptimizer.CloudflareDnsException
import com.cfoptimizer.CloudflareTransport

private const val ZONE_ID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
private const val RECORD_ID = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
private const val TOKEN = "test_token_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

fun main() {
    var passed = 0
    var failed = 0
    fun check(name: String, condition: Boolean, detail: String = "") {
        if (condition) { passed++; println("PASS  $name") }
        else { failed++; println("FAIL  $name  $detail") }
    }
    fun fails(name: String, block: () -> Unit) {
        try {
            block()
            check(name, false, "未抛出异常")
        } catch (_: CloudflareDnsException) {
            check(name, true)
        }
    }

    run {
        val calls = mutableListOf<Triple<String, String, Map<String, Any?>?>>()
        val transport = CloudflareTransport { method, path, payload ->
            calls.add(Triple(method, path, payload))
            if (method == "GET") mapOf("success" to true, "result" to emptyList<Any>())
            else mapOf("success" to true, "result" to mapOf("id" to RECORD_ID))
        }
        val result = CloudflareDns.upsertCname(
            apiToken = TOKEN,
            zoneId = ZONE_ID,
            zoneName = "example.com",
            recordName = "edge",
            target = "preferred.example.net",
            transport = transport
        )
        check("不存在时创建 CNAME", result.operation == "created" && result.name == "edge.example.com", result.toString())
        check("默认 DNS only", calls.last().third?.get("proxied") == false, calls.last().toString())
        check("创建使用 POST", calls.last().first == "POST", calls.last().toString())
    }

    run {
        val calls = mutableListOf<String>()
        val transport = CloudflareTransport { method, _, _ ->
            calls.add(method)
            if (method == "GET") mapOf(
                "success" to true,
                "result" to listOf(mapOf(
                    "id" to RECORD_ID, "type" to "CNAME", "name" to "edge.example.com",
                    "content" to "old.example.net", "proxied" to false, "ttl" to 1
                ))
            ) else mapOf("success" to true, "result" to mapOf("id" to RECORD_ID))
        }
        val result = CloudflareDns.upsertCname(
            TOKEN, "edge.example.com", "new.example.net", ZONE_ID, "example.com", transport = transport
        )
        check("已有 CNAME 使用 PATCH 更新", result.operation == "updated" && calls == listOf("GET", "PATCH"), calls.toString())
    }

    run {
        val calls = mutableListOf<String>()
        val transport = CloudflareTransport { method, _, _ ->
            calls.add(method)
            mapOf(
                "success" to true,
                "result" to listOf(mapOf(
                    "id" to RECORD_ID, "type" to "CNAME", "name" to "edge.example.com",
                    "content" to "same.example.net", "proxied" to false, "ttl" to 1
                ))
            )
        }
        val result = CloudflareDns.upsertCname(
            TOKEN, "edge.example.com", "same.example.net", ZONE_ID, "example.com", transport = transport
        )
        check("相同 CNAME 不写入", result.operation == "unchanged" && calls == listOf("GET"), calls.toString())
    }

    run {
        val conflict = CloudflareTransport { _, _, _ -> mapOf(
            "success" to true,
            "result" to listOf(mapOf(
                "id" to RECORD_ID, "type" to "A", "name" to "edge.example.com", "content" to "192.0.2.1"
            ))
        ) }
        fails("同名 A/AAAA 冲突时停止") {
            CloudflareDns.upsertCname(
                TOKEN, "edge.example.com", "preferred.example.net", ZONE_ID, "example.com", transport = conflict
            )
        }
    }

    run {
        val transport = CloudflareTransport { method, path, _ ->
            when {
                method == "GET" && path.startsWith("/zones?") -> mapOf(
                    "success" to true,
                    "result" to listOf(mapOf("id" to ZONE_ID, "name" to "example.com"))
                )
                method == "GET" -> mapOf("success" to true, "result" to emptyList<Any>())
                else -> mapOf("success" to true, "result" to mapOf("id" to RECORD_ID))
            }
        }
        val result = CloudflareDns.upsertCname(
            TOKEN, "edge", "preferred.example.net", zoneName = "example.com", transport = transport
        )
        check("可按区域域名查询 Zone", result.zoneId == ZONE_ID, result.toString())
    }

    fails("拒绝 CNAME 自循环") {
        val transport = CloudflareTransport { _, _, _ -> mapOf("success" to true, "result" to emptyList<Any>()) }
        CloudflareDns.upsertCname(TOKEN, "edge.example.com", "edge.example.com", ZONE_ID, "example.com", transport = transport)
    }

    println("CloudflareDnsTest：PASS $passed / FAIL $failed")
    if (failed > 0) kotlin.system.exitProcess(1)
}
