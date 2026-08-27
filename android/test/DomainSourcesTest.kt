import com.cfoptimizer.DomainParseResult
import com.cfoptimizer.DomainSourceException
import com.cfoptimizer.DomainSources
import com.cfoptimizer.DomainSubscription
import com.cfoptimizer.SubscriptionResolver
import java.net.InetAddress
import java.util.Base64

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
        } catch (_: DomainSourceException) {
            check(name, true)
        }
    }

    val plain = DomainSources.parse(
        "# comment\nEXAMPLE.com\nhttps://cdn.Example.net/path\nexample.com\n127.0.0.1\n"
    )
    check("TXT URL/注释/去重", plain.domains == listOf("example.com", "cdn.example.net"), plain.toString())
    check("TXT 无效字段计数", plain.ignored == 1, "got ${plain.ignored}")

    val csv = DomainSources.parse("label,domain,note\nA,one.example,first\nB,two.example,second\n", "wrong.txt")
    check("按内容识别 CSV 表头", csv.sourceFormat == "CSV" && csv.domains == listOf("one.example", "two.example"), csv.toString())

    val tsv = DomainSources.parse("name\thostname\nA\tone.example\nB\ttwo.example\n")
    check("按内容识别 TSV", tsv.sourceFormat == "TSV" && tsv.domains.size == 2, tsv.toString())

    val json = DomainSources.parse("{\"data\":[{\"hostname\":\"one.example\"},{\"domain\":\"two.example\"}]}")
    check("JSON 支持嵌套对象", json.sourceFormat == "JSON" && json.domains == listOf("one.example", "two.example"), json.toString())
    fails("拒绝非标准 JSON 数字") { DomainSources.parse("{\"domains\":[\"one.example\"],\"bad\":+1}") }

    val encoded = Base64.getEncoder().encodeToString("one.example\ntwo.example\n".toByteArray())
    val base64 = DomainSources.parse(encoded)
    check("Base64 包裹 TXT", base64.sourceFormat == "Base64 + TXT" && base64.domains.size == 2, base64.toString())

    check("IDN 转 Punycode", DomainSources.normalizeDomain("例子.测试") == "xn--fsqu00a.xn--0zwm56d")
    fails("拒绝 IP 地址") { DomainSources.normalizeDomain("192.0.2.1") }
    fails("拒绝通配符") { DomainSources.normalizeDomain("*.example.com") }
    fails("拒绝二进制文件") { DomainSources.parseBytes(byteArrayOf(65, 0, 66), "domains.txt") }

    val selected = DomainSources.chooseCandidates(
        builtin = listOf("www.nexusmods.com", "builtin.example"),
        custom = listOf("one.example", "two.example"),
        customMode = true
    )
    check("自定义模式不混入内置/基准", selected == listOf("one.example", "two.example"), selected.toString())

    val publicResolver = SubscriptionResolver { listOf(InetAddress.getByName("93.184.216.34")) }
    val validated = DomainSubscription.validateUrl("https://example.com/list.txt#ignored", publicResolver)
    check("订阅仅保留安全 URL", validated.uri.toString() == "https://example.com/list.txt", validated.uri.toString())
    val encodedUrl = DomainSubscription.validateUrl("https://example.com/a%2Fb?next=%2Fedge#ignored", publicResolver)
    check(
        "订阅保留编码路径和查询",
        encodedUrl.uri.rawPath == "/a%2Fb" && encodedUrl.uri.rawQuery == "next=%2Fedge",
        encodedUrl.uri.toString()
    )
    val privateResolver = SubscriptionResolver { listOf(InetAddress.getByName("127.0.0.1")) }
    fails("订阅拒绝本机地址") { DomainSubscription.validateUrl("https://example.com/list", privateResolver) }
    fails("订阅拒绝非 80/443 端口") { DomainSubscription.validateUrl("https://example.com:8080/list", publicResolver) }
    check("CGNAT 不是公网订阅目标", !DomainSubscription.isPublicAddress(InetAddress.getByName("100.64.0.1")))
    check("文档 IPv6 不是公网订阅目标", !DomainSubscription.isPublicAddress(InetAddress.getByName("2001:db8::1")))
    check("普通公网地址允许", DomainSubscription.isPublicAddress(InetAddress.getByName("1.1.1.1")))

    println("DomainSourcesTest：PASS $passed / FAIL $failed")
    if (failed > 0) kotlin.system.exitProcess(1)
}
