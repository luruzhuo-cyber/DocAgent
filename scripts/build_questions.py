import json, re
from pathlib import Path

spec = """query-params|query-parameters|URL 里查询字符串从哪个符号开始，各键值对如何分隔？|从 ? 后开始，以 & 分隔。|?;&
query-params|query-parameters|查询参数声明 int 后，URL 里的字符串会怎样处理？|转换为声明的类型并进行校验。|转换;校验
query-params|defaults|未传分页参数时，示例中的 skip 和 limit 各是多少？|skip=0，limit=10。|0;10
query-params|defaults|示例只传 skip=20 而不传 limit，最后使用什么 limit？|使用默认 limit=10。|10
query-params|optional-parameters|怎样设置默认值才能让查询参数可选？|将默认值设为 None。|None
query-params|query-parameter-type-conversion|short=yes 能转换成布尔真吗？还有哪些写法？|可以，1、True、true、on、yes 都会转换为 True。|True
query-params|required-query-parameters|不想给查询参数默认值而希望客户端必须提供，应怎样声明？|不声明默认值即可使它成为必选参数。|默认值
body|request-body|请求体和响应体分别由哪一方发给哪一方？|请求体由客户端发给 API，响应体由 API 发给客户端。|客户端;API
body|request-body|文档建议用哪个最常见 HTTP 方法发送数据？|POST 最常见，也可使用 PUT、DELETE 或 PATCH。|POST
body|request-body|为何不推荐给 GET 请求附加请求体？|规范未定义其行为，Swagger UI 不显示此文档，代理也可能不支持。|Swagger;代理
body|import-pydantics-basemodel|声明请求模型前应从什么包导入哪个基类？|从 pydantic 导入 BaseModel。|pydantic;BaseModel
body|create-your-data-model|请求模型的属性什么情况下可选？|包含默认值时可选，例如默认值为 None。|默认值;None
body|results|把函数参数声明为 Item 模型后，无效请求体会发生什么？|进行校验并返回指出错误位置和内容的错误信息。|校验;错误
body|automatic-docs|请求模型的 JSON Schema 会进入哪一种 API 规范并展示在哪里？|成为 OpenAPI Schema 的一部分，并显示于交互式 API 文档。|OpenAPI
body|editor-support|与直接接收 dict 相比，接收 Pydantic 模型给编辑器带来什么？|属性类型提示、补全及错误类型操作检查。|补全
path-params|path-parameters-with-types|路径参数 item_id 要按整数解析，应该标注什么类型？|使用 Python int 类型注解。|int
path-params|data-conversion|访问 /items/3 后，整数声明的 item_id 是数字还是字符串？|为整数 3，而不是字符串。|3
path-params|data-validation|item_id 声明 int，却访问 /items/foo，会出现什么？|数据校验失败，返回指出路径 item_id 的整数解析错误。|item_id
path-params|order-matters|/users/me 与 /users/{user_id} 应先声明哪一个，为什么？|先声明 /users/me，路径操作按顺序匹配。|/users/me
path-params|pydantic|FastAPI 的数据校验底层使用哪个库？|Pydantic。|Pydantic
path-params|standards-based-benefits-alternative-documentation|除 Swagger UI 外还能访问哪个路径查看 ReDoc？|/redoc。|/redoc
path-params|predefined-values|路径参数只能取有限预设值时可用哪种 Python 类型？|使用 Enum 枚举。|Enum
response-status-code|response-status-code|status_code 应写在路由装饰器还是业务函数的参数中？|写在 get、post 等装饰器方法中。|装饰器
response-status-code|response-status-code|status_code 除数字外还能接收哪种枚举？|IntEnum，例如 http.HTTPStatus。|IntEnum
response-status-code|about-http-status-codes|成功响应的默认状态码是多少？|200。|200
response-status-code|about-http-status-codes|创建新数据库记录后通常使用哪个状态码？|201，表示已创建。|201
response-status-code|about-http-status-codes|204 响应允许包含响应体吗？|不允许，204 表示无内容。|204
response-status-code|about-http-status-codes|HTTP 客户端错误和服务端错误分别属于哪个数值区间？|客户端 400–499，服务器 500–599。|400;499;500;599
handling-errors|raise-an-httpexception-in-your-code|应 raise 还是 return HTTPException，抛出后会怎样？|应 raise，立即终止执行并向客户端发送错误。|raise
handling-errors|the-resulting-response|请求不存在的示例 item bar，会收到什么状态码？|404。|404
handling-errors|add-custom-headers|HTTPException 能否在错误响应中附带自定义响应头？|可以添加自定义响应头。|可以
handling-errors|override-the-default-exception-handlers|请求中的数据无效时 FastAPI 抛出什么异常？|RequestValidationError。|RequestValidationError
security-first-steps|fastapis-oauth2passwordbearer|OAuth2PasswordBearer 的 tokenUrl 参数表示什么？|客户端发送用户名和密码以获取令牌的 URL。|令牌
security-first-steps|fastapis-oauth2passwordbearer|设置 tokenUrl 会自动创建获取令牌的端点吗？|不会，仅声明 URL 并用于 OpenAPI。|不会
security-first-steps|fastapis-oauth2passwordbearer|API 根路径为 /api/v1/ 时，相对 tokenUrl=token 指向哪里？|/api/v1/token。|/api/v1/token
security-first-steps|what-it-does|OAuth2PasswordBearer 会在哪个请求头寻找哪种令牌？|Authorization 请求头中的 Bearer 令牌。|Authorization;Bearer
security-first-steps|what-it-does|缺少 Authorization 请求头时会直接返回哪个状态码？|401。|401
security-first-steps|what-it-does|拿到 Bearer 字符串就代表令牌有效性已验证了吗？|没有，此阶段尚未验证令牌是否有效。|验证
first-steps|interactive-api-docs|交互式 API 文档应该访问哪个 URL 路径？|/docs。|/docs
dependencies-index|to-async-or-not-to-async|同步路径函数能依赖 async def 函数吗？|可以，同步与异步依赖可以混用。|可以"""
rows = []
for line in spec.splitlines():
    doc, anchor, question, answer, phrases = line.split("|")
    text = Path("corpus", doc + ".md").read_text(encoding="utf-8")
    heading = next(
        h
        for h in re.findall(r"^#{1,6} (.+)$", text, re.M)
        if "{ #" + anchor + " }" in h
    )
    rows.append(
        dict(
            question=question,
            kind="single",
            expected_evidence=[dict(document=doc + ".md", section=heading)],
            reference_answer=answer,
            expected_phrases=phrases.split(";"),
        )
    )
old = [
    json.loads(l)
    for l in Path("eval/questions.jsonl").read_text(encoding="utf-8").splitlines()
]
answers = [
    "路径占位符对应路径参数，未在路径中的普通函数参数会解释为查询参数。",
    "Pydantic 模型参数解释为请求体，路径中匹配的为路径参数，其他单值参数为查询参数，可以同时使用。",
    "在装饰器设置 status_code 声明正常状态码，在错误场景 raise HTTPException。",
    "OAuth2PasswordBearer 实例是可调用对象，可以作为 Depends 的依赖，返回令牌字符串。",
    "运行 fastapi dev，通过 /docs 查看交互文档，安全方案会集成在文档中。",
]
for r, answer in zip(old[40:45], answers):
    r["reference_answer"] = answer
    rows.append(r)
for q, doc, anchor, answer, expr in [
    (
        "检索分页示例只传 skip=20 时的 skip 和默认 limit，用计算工具求二者之和。",
        "query-params",
        "defaults",
        "30",
        "20+10",
    ),
    (
        "先查第一个应用示例监听的本地端口，再用计算工具加 1。",
        "first-steps",
        "first-steps",
        "8001",
        "8000+1",
    ),
    (
        "先查未找到和默认成功响应的状态码，再用计算工具求前者减后者。",
        "response-status-code",
        "about-http-status-codes",
        "204",
        "404-200",
    ),
]:
    text = Path("corpus", doc + ".md").read_text(encoding="utf-8")
    heading = next(
        h
        for h in re.findall(r"^#{1,6} (.+)$", text, re.M)
        if "{ #" + anchor + " }" in h
    )
    rows.append(
        dict(
            question=q,
            kind="calculation",
            expected_evidence=[dict(document=doc + ".md", section=heading)],
            reference_answer=answer,
            expected_phrases=[answer],
            expression=expr,
        )
    )
for r in old[48:]:
    r["reference_answer"] = "资料不足，应拒绝猜测。"
    rows.append(r)
assert len(rows) == 50
# Stratify: test 12 singles + 1 multi + 1 calculation + 1 unanswerable.
test = set(range(2, 38, 3)) | {44, 47, 49}
assert len(test) == 15
for i, r in enumerate(rows):
    r.update(
        id=f"Q{i+1:02}",
        split="test" if i in test else "dev",
        manual_reviewed=False,
        label_origin="agent-authored and source-audited against pinned official prose; not human reviewed",
    )
Path("eval/questions.jsonl").write_text(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
)
