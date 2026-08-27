package com.cfoptimizer

import java.net.IDN
import java.net.Inet6Address
import java.net.InetAddress
import java.net.URI
import java.nio.ByteBuffer
import java.nio.charset.CharacterCodingException
import java.nio.charset.CodingErrorAction
import java.nio.charset.Charset
import java.util.Base64
import java.util.Locale

class DomainSourceException(message: String) : IllegalArgumentException(message)

data class DomainParseResult(
    val domains: List<String>,
    val sourceFormat: String,
    val ignored: Int = 0,
    val warnings: List<String> = emptyList()
)

/** Content-based domain source detection shared by manual input, files and subscriptions. */
object DomainSources {
    const val MAX_SOURCE_BYTES = 1_048_576
    const val MAX_DOMAINS = 5_000

    private val domainLabel = Regex("^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    private val ipv4Literal = Regex("^(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})$")
    private val jsonDomainKeys = setOf("domain", "host", "hostname", "address", "target", "content", "name")
    private val jsonListKeys = setOf("domains", "hosts", "items", "data", "results", "entries")
    private val csvDomainHeaders = setOf("domain", "host", "hostname", "address", "target", "域名", "主机名")

    fun normalizeDomain(value: String): String {
        var raw = value.trim()
            .trim('"', '\'', '`', '[', ']', '(', ')', '{', '}', '<', '>')
            .trimEnd('.')
        if (raw.isEmpty()) throw DomainSourceException("域名为空")
        if (raw.startsWith("*.")) throw DomainSourceException("不支持通配符域名")

        val parsedHost = when {
            raw.contains("://") -> {
                val uri = try { URI(raw) } catch (_: Exception) {
                    throw DomainSourceException("只接受域名或 HTTP/HTTPS 地址")
                }
                if (uri.scheme?.lowercase(Locale.ROOT) !in setOf("http", "https")) {
                    throw DomainSourceException("只接受域名或 HTTP/HTTPS 地址")
                }
                uriHost(uri)
            }
            raw.any { it == '/' || it == '?' || it == '#' } -> {
                val uri = try { URI("//$raw") } catch (_: Exception) {
                    throw DomainSourceException("域名格式无效")
                }
                uriHost(uri)
            }
            raw.count { it == ':' } == 1 && raw.substringAfterLast(':').all { it.isDigit() } ->
                raw.substringBeforeLast(':')
            else -> ""
        }
        if (parsedHost.isNotEmpty()) raw = parsedHost
        raw = raw.trim().trimEnd('.').lowercase(Locale.ROOT)
        if (raw.isEmpty()) throw DomainSourceException("域名格式无效")
        if (isIpLiteral(raw)) throw DomainSourceException("IP 地址不是候选域名")

        val asciiName = try {
            IDN.toASCII(raw, IDN.USE_STD3_ASCII_RULES).lowercase(Locale.ROOT)
        } catch (_: Exception) {
            throw DomainSourceException("域名编码无效")
        }
        if (asciiName.length > 253 || !asciiName.contains('.')) {
            throw DomainSourceException("请输入完整域名")
        }
        if (asciiName.split('.').any { !domainLabel.matches(it) }) {
            throw DomainSourceException("域名格式无效")
        }
        return asciiName
    }

    fun chooseCandidates(builtin: List<String>, custom: List<String>, customMode: Boolean): List<String> =
        (if (customMode) custom else builtin).map { it.trim().lowercase(Locale.ROOT) }
            .filter { it.isNotEmpty() }.distinct()

    fun parseBytes(payload: ByteArray, filename: String = ""): DomainParseResult =
        parse(decodeBytes(payload), filename)

    fun decodeBytes(payload: ByteArray): String {
        if (payload.size > MAX_SOURCE_BYTES) throw DomainSourceException("域名源文件不能超过 1 MiB")
        if (payload.any { it == 0.toByte() }) {
            throw DomainSourceException("检测到二进制内容，只支持文本域名源")
        }
        val charsets = listOf(Charsets.UTF_8, Charset.forName("GB18030"))
        for (charset in charsets) {
            try {
                val decoder = charset.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                return decoder.decode(ByteBuffer.wrap(payload)).toString().removePrefix("\uFEFF")
            } catch (_: CharacterCodingException) {
                // Try the next supported text encoding.
            }
        }
        throw DomainSourceException("文件编码无法识别，请使用 UTF-8 文本")
    }

    fun parse(text: String, filename: String = "", allowBase64: Boolean = true): DomainParseResult {
        if (text.toByteArray(Charsets.UTF_8).size > MAX_SOURCE_BYTES) {
            throw DomainSourceException("域名源文件不能超过 1 MiB")
        }
        if (text.indexOf('\u0000') >= 0) {
            throw DomainSourceException("检测到二进制内容，只支持文本域名源")
        }
        val stripped = text.trimStart('\uFEFF', ' ', '\t', '\r', '\n')
        if (stripped.isEmpty()) throw DomainSourceException("域名源内容为空")

        var sourceFormat = "TXT"
        val values: List<String>
        if (stripped.startsWith('[') || stripped.startsWith('{')) {
            val parsed = try { SimpleJson.parse(stripped) } catch (_: Exception) {
                throw DomainSourceException("JSON 格式无效")
            }
            values = jsonValues(parsed)
            sourceFormat = "JSON"
            if (values.isEmpty()) {
                throw DomainSourceException("JSON 中未找到 domains/host/domain 等受支持字段")
            }
        } else {
            val decoded = if (allowBase64) tryBase64(stripped) else null
            if (decoded != null) {
                val inner = parse(decoded, filename, allowBase64 = false)
                return inner.copy(sourceFormat = "Base64 + ${inner.sourceFormat}")
            }
            val csv = csvValues(stripped)
            if (csv != null) {
                values = csv.first
                sourceFormat = csv.second
            } else {
                values = plainValues(stripped)
                val suffix = filename.substringAfterLast('.', "").lowercase(Locale.ROOT)
                if (suffix in setOf("csv", "tsv", "json")) {
                    sourceFormat = "TXT（内容与 .$suffix 扩展名不一致）"
                }
            }
        }

        val domains = ArrayList<String>()
        val seen = LinkedHashSet<String>()
        var ignored = 0
        for (value in values) {
            val domain = try { normalizeDomain(value) } catch (_: DomainSourceException) {
                ignored++
                continue
            }
            if (seen.add(domain)) domains.add(domain)
            if (domains.size > MAX_DOMAINS) {
                throw DomainSourceException("域名数量不能超过 $MAX_DOMAINS 个")
            }
        }
        if (domains.isEmpty()) {
            throw DomainSourceException("没有识别到有效域名；支持 TXT、CSV、TSV、JSON 和 Base64 文本")
        }
        val warnings = if (ignored > 0) listOf("已忽略 $ignored 个非域名字段") else emptyList()
        return DomainParseResult(domains, sourceFormat, ignored, warnings)
    }

    private fun uriHost(uri: URI): String {
        uri.host?.let { return it }
        var authority = uri.rawAuthority.orEmpty().substringAfterLast('@')
        if (authority.startsWith('[')) return authority.substringAfter('[', "").substringBefore(']')
        val port = authority.substringAfterLast(':', "")
        if (authority.count { it == ':' } == 1 && port.all { it.isDigit() }) {
            authority = authority.substringBeforeLast(':')
        }
        return authority
    }

    private fun isIpLiteral(value: String): Boolean {
        val match = ipv4Literal.matchEntire(value)
        if (match != null) return match.groupValues.drop(1).all { it.toIntOrNull() in 0..255 }
        if (!value.contains(':') || !value.all { it in "0123456789abcdefABCDEF:." }) return false
        return try { InetAddress.getByName(value) is Inet6Address } catch (_: Exception) { false }
    }

    private fun jsonValues(value: Any?): List<String> {
        if (value is String) return listOf(value)
        if (value is List<*>) {
            return value.flatMap { item -> if (item is String || item is Map<*, *>) jsonValues(item) else emptyList() }
        }
        if (value !is Map<*, *>) return emptyList()
        val output = ArrayList<String>()
        for ((key, item) in value) {
            val normalizedKey = key?.toString()?.lowercase(Locale.ROOT) ?: continue
            if (normalizedKey in jsonDomainKeys && item is String) output.add(item)
        }
        for ((key, item) in value) {
            val normalizedKey = key?.toString()?.lowercase(Locale.ROOT) ?: continue
            if (normalizedKey in jsonListKeys) output.addAll(jsonValues(item))
        }
        return output
    }

    private fun csvValues(text: String): Pair<List<String>, String>? {
        val sample = text.take(8192)
        if (!sample.contains('\n') && listOf(',', '\t', ';').none { sample.contains(it) }) return null
        val counts = mapOf(',' to sample.count { it == ',' }, '\t' to sample.count { it == '\t' }, ';' to sample.count { it == ';' })
        val delimiter = counts.maxByOrNull { it.value }?.key ?: ','
        val rows = parseDelimited(text, delimiter)
        if (rows.isEmpty() || (rows.maxOfOrNull { it.size } ?: 0) < 2) return null
        val headers = rows.first().map { it.trim().lowercase(Locale.ROOT) }
        val headerIndex = headers.indexOfFirst { it in csvDomainHeaders }
        val values = if (headerIndex >= 0) {
            rows.drop(1).mapNotNull { row -> row.getOrNull(headerIndex) }
        } else {
            rows.flatten()
        }
        return values to if (delimiter == '\t') "TSV" else "CSV"
    }

    private fun parseDelimited(text: String, delimiter: Char): List<List<String>> {
        val rows = ArrayList<List<String>>()
        var row = ArrayList<String>()
        val cell = StringBuilder()
        var quoted = false
        var index = 0
        while (index < text.length) {
            val ch = text[index]
            when {
                quoted && ch == '"' && index + 1 < text.length && text[index + 1] == '"' -> {
                    cell.append('"'); index++
                }
                ch == '"' -> quoted = !quoted
                !quoted && ch == delimiter -> { row.add(cell.toString()); cell.setLength(0) }
                !quoted && ch == '\n' -> {
                    row.add(cell.toString().trimEnd('\r')); cell.setLength(0)
                    rows.add(row); row = ArrayList()
                }
                else -> cell.append(ch)
            }
            index++
        }
        if (cell.isNotEmpty() || row.isNotEmpty()) {
            row.add(cell.toString().trimEnd('\r'))
            rows.add(row)
        }
        return rows
    }

    private fun plainValues(text: String): List<String> {
        val output = ArrayList<String>()
        for (rawLine in text.lineSequence()) {
            var line = rawLine.trim()
            if (line.isEmpty() || line.startsWith('#') || line.startsWith(';') || line.startsWith("//")) continue
            line = line.replace(Regex("\\s+#.*$"), "")
            output.addAll(line.split(Regex("[\\s,;|]+" )).filter { it.isNotEmpty() })
        }
        return output
    }

    private fun tryBase64(text: String): String? {
        val compact = text.filterNot { it.isWhitespace() }
        if (compact.length < 16 || compact.length % 4 == 1 || compact.contains('.')) return null
        if (!Regex("^[A-Za-z0-9_+/=-]+$").matches(compact)) return null
        val padded = compact.replace('-', '+').replace('_', '/') + "=".repeat((4 - compact.length % 4) % 4)
        return try { decodeBytes(Base64.getDecoder().decode(padded)) } catch (_: Exception) { null }
    }
}

/** Small dependency-free JSON codec so CLI builds and JVM tests use the same parser as Android. */
object SimpleJson {
    fun parse(text: String): Any? = Parser(text).parse()

    fun stringify(value: Any?): String = when (value) {
        null -> "null"
        is String -> "\"${escape(value)}\""
        is Boolean, is Number -> value.toString()
        is Map<*, *> -> value.entries.joinToString(prefix = "{", postfix = "}") {
            "\"${escape(it.key.toString())}\":${stringify(it.value)}"
        }
        is Iterable<*> -> value.joinToString(prefix = "[", postfix = "]") { stringify(it) }
        is Array<*> -> value.joinToString(prefix = "[", postfix = "]") { stringify(it) }
        else -> "\"${escape(value.toString())}\""
    }

    private fun escape(value: String): String = buildString {
        for (ch in value) {
            when (ch) {
                '\\' -> append("\\\\")
                '"' -> append("\\\"")
                '\b' -> append("\\b")
                '\u000C' -> append("\\f")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> if (ch.code < 0x20) append("\\u%04x".format(ch.code)) else append(ch)
            }
        }
    }

    private class Parser(private val source: String) {
        private var index = 0

        fun parse(): Any? {
            val value = value()
            whitespace()
            if (index != source.length) error("trailing JSON")
            return value
        }

        private fun value(): Any? {
            whitespace()
            if (index >= source.length) error("unexpected end")
            return when (source[index]) {
                '{' -> obj()
                '[' -> array()
                '"' -> string()
                't' -> literal("true", true)
                'f' -> literal("false", false)
                'n' -> literal("null", null)
                else -> number()
            }
        }

        private fun obj(): Map<String, Any?> {
            expect('{')
            val result = LinkedHashMap<String, Any?>()
            whitespace()
            if (peek('}')) { index++; return result }
            while (true) {
                whitespace()
                val key = string()
                whitespace(); expect(':')
                result[key] = value()
                whitespace()
                if (peek('}')) { index++; return result }
                expect(',')
            }
        }

        private fun array(): List<Any?> {
            expect('[')
            val result = ArrayList<Any?>()
            whitespace()
            if (peek(']')) { index++; return result }
            while (true) {
                result.add(value())
                whitespace()
                if (peek(']')) { index++; return result }
                expect(',')
            }
        }

        private fun string(): String {
            expect('"')
            val result = StringBuilder()
            while (index < source.length) {
                val ch = source[index++]
                if (ch == '"') return result.toString()
                if (ch != '\\') {
                    if (ch.code < 0x20) error("control character in string")
                    result.append(ch)
                    continue
                }
                if (index >= source.length) error("bad escape")
                when (val escaped = source[index++]) {
                    '"', '\\', '/' -> result.append(escaped)
                    'b' -> result.append('\b')
                    'f' -> result.append('\u000C')
                    'n' -> result.append('\n')
                    'r' -> result.append('\r')
                    't' -> result.append('\t')
                    'u' -> {
                        if (index + 4 > source.length) error("bad unicode escape")
                        result.append(source.substring(index, index + 4).toInt(16).toChar())
                        index += 4
                    }
                    else -> error("bad escape")
                }
            }
            error("unterminated string")
        }

        private fun number(): Number {
            val start = index
            while (index < source.length && source[index] in "-+0123456789.eE") index++
            if (start == index) error("expected value")
            val raw = source.substring(start, index)
            if (!Regex("-?(?:0|[1-9]\\d*)(?:\\.\\d+)?(?:[eE][+-]?\\d+)?").matches(raw)) {
                error("bad number")
            }
            return raw.toLongOrNull() ?: raw.toDoubleOrNull() ?: error("bad number")
        }

        private fun <T> literal(word: String, value: T): T {
            if (!source.startsWith(word, index)) error("bad literal")
            index += word.length
            return value
        }

        private fun whitespace() { while (index < source.length && source[index].isWhitespace()) index++ }
        private fun peek(ch: Char): Boolean = index < source.length && source[index] == ch
        private fun expect(ch: Char) { if (!peek(ch)) error("expected $ch"); index++ }
    }
}
