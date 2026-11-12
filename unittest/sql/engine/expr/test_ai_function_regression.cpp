// Run: python3 unittest/sql/engine/expr/run_ai_function_regression.py
// Standalone checks linked with the regular seekdb libraries.
#include "sql/engine/expr/ob_expr_ai/ob_ai_func_utils.h"
#include "share/ai_service/ob_ai_service_struct.h"
#include "share/inner_table/ob_inner_table_schema.h"
#include "share/schema/ob_table_schema.h"
#include "share/ob_dml_sql_splicer.h"
#include "sql/engine/expr/ob_expr_ai/ob_ai_func_client.h"
#include <cstdio>
#include <string>
using namespace oceanbase::common;
using namespace oceanbase::share;
static int checks = 0;
static int failures = 0;
static void expect(bool value, const char *name)
{
  ++checks;
  if (!value) ++failures;
  std::printf("%s %s\n", value ? "PASS" : "FAIL", name);
}
static ObJsonObject *object(ObArenaAllocator &allocator, const std::string &text)
{
  ObString json(static_cast<int32_t>(text.size()), text.data());
  ObIJsonBase *base = nullptr;
  if (ObJsonBaseFactory::get_json_base(&allocator, json, ObJsonInType::JSON_TREE,
                                    ObJsonInType::JSON_TREE, base) != OB_SUCCESS) return nullptr;
  return static_cast<ObJsonObject *>(base);
}
static void render(const char *name, const std::string &json, const std::string &expected,
                   int expected_ret = OB_SUCCESS)
{
  ObArenaAllocator allocator;
  ObString out;
  int ret = ObAIFuncPromptObjectUtils::replace_all_str_args_in_template(allocator, object(allocator, json), out);
  expect(ret == expected_ret && (ret != OB_SUCCESS || std::string(out.ptr(), out.length()) == expected), name);
}
int main()
{
  {
    oceanbase::share::schema::ObTableSchema table;
    expect(ObInnerTableSchema::all_ai_model_endpoint_schema(table) == OB_SUCCESS,
           "generated endpoint table schema");
    const auto *column = table.get_column_schema("max_concurrency");
    expect(column != nullptr && column->get_column_id() == 30 && column->get_orig_default_value().get_int() == 16,
           "concurrency column has persistent default");
    oceanbase::share::schema::ObTableSchema view;
    expect(ObInnerTableSchema::dba_ob_ai_model_endpoints_schema(view) == OB_SUCCESS &&
           std::string(view.get_view_schema().get_view_definition_str().ptr(), view.get_view_schema().get_view_definition_str().length()).find("MAX_CONCURRENCY") != std::string::npos,
           "generated endpoint view exposes concurrency");
  }
  for (const char *value : {"1", "3", "7", "1024"}) {
    ObArenaAllocator allocator;
    ObAiModelEndpointInfo info, copy;
    auto *json = object(allocator, std::string(R"({"ai_model_name":"m","url":"http://127.0.0.1","access_key":"k","provider":"openai","max_concurrency":)") + value + "}");
    int ret = info.parse_from_json_base(allocator, ObString("ep"), *json);
    expect(ret == OB_SUCCESS && info.get_max_concurrency() == std::stoll(value), "valid endpoint concurrency");
    expect(copy.deep_copy(allocator, info) == OB_SUCCESS && copy.get_max_concurrency() == info.get_max_concurrency(), "deep-copy endpoint concurrency");
    json = object(allocator, R"({"url":"http://127.0.0.1/updated"})");
    expect(info.merge_delta_endpoint(allocator, *json) == OB_SUCCESS && info.get_max_concurrency() == std::stoll(value), "partial ALTER preserves concurrency");
  }
  for (const char *value : {"0", "-1", "1025", "1.5", "true", "null", "\"8\"", "[]", "{}"}) {
    ObArenaAllocator allocator;
    ObAiModelEndpointInfo info;
    auto *json = object(allocator, std::string(R"({"ai_model_name":"m","url":"http://127.0.0.1","access_key":"k","provider":"openai","max_concurrency":)") + value + "}");
    expect(info.parse_from_json_base(allocator, ObString("ep"), *json) == OB_AI_FUNC_PARAM_VALUE_INVALID, "invalid endpoint concurrency");
  }
  for (const char *provider : {"ollama", "Ollama", "OLLAMA"}) {
    ObArenaAllocator allocator;
    ObAiModelEndpointInfo info;
    auto *json = object(allocator, std::string(R"({"ai_model_name":"m","url":"http://127.0.0.1","access_key":"","provider":")") + provider + "\"}");
    expect(info.parse_from_json_base(allocator, ObString("ep"), *json) == OB_SUCCESS, "Ollama allows empty API key");
    ObString key;
    expect(info.get_unencrypted_access_key(allocator, key) == OB_SUCCESS && key.empty(), "Ollama empty credential round-trip");
    ObDMLSqlSplicer sql;
    ObSqlString statement;
    expect(sql.add_column("access_key", ObHexEscapeSqlStr(key.empty() ? ObString("") : key)) == OB_SUCCESS &&
           sql.splice_insert_sql("endpoint", statement) == OB_SUCCESS &&
           std::string(statement.ptr(), statement.length()).find("NULL") == std::string::npos,
           "empty credential SQL remains a string");
    ObAIFuncIComplete *complete = nullptr;
    ObAIFuncIEmbed *embed = nullptr;
    ObString name(provider);
    expect(ObAIFuncUtils::get_complete_provider(allocator, name, complete) == OB_SUCCESS, "Ollama completion routing");
    expect(ObAIFuncUtils::get_embed_provider(allocator, name, embed) == OB_SUCCESS, "Ollama embedding routing");
    ObString model("m"), prompt, content("中文😀");
    ObJsonObject *body = nullptr;
    expect(complete->get_body(allocator, model, prompt, content, nullptr, body) == OB_SUCCESS &&
           body->get_value("stream") != nullptr && !body->get_value("stream")->get_boolean(), "Ollama disables streaming");
    ObArray<ObString> headers;
    ObString empty;
    expect(complete->get_header(allocator, empty, headers) == OB_SUCCESS && headers.count() == 1 &&
           headers.at(0) == ObString("Content-Type: application/json"), "Ollama content type without authorization");
    ObAIFuncClient client;
    ObString url("http://127.0.0.1:18081/api/generate");
    expect(client.init(allocator, url, headers) == OB_SUCCESS, "Ollama HTTP client initialization");
  }
  {
    ObArenaAllocator allocator;
    ObAiModelEndpointInfo info;
    auto *json = object(allocator, R"({"ai_model_name":"m","url":"http://127.0.0.1","access_key":"","provider":"openai"})");
    expect(info.parse_from_json_base(allocator, ObString("ep"), *json) == OB_AI_FUNC_PARAM_EMPTY, "OpenAI still requires key");
  }
  render("repeat and reorder", R"({"template":"{1}/{0}/{1}","args":["a","b"]})", "b/a/b");
  render("nested JSON prompt", R"({"template":"{0}","args":[{"template":"内{0}","args":[{"k":[1,true,null]}]}]})", "内{\"k\": [1, true, null]}");
  render("literal braces", R"({"template":"{abc} {} {{ }}", "args":[]})", "{abc} {} {{ }}");
  render("index overflow", R"({"template":"{18446744073709551616}","args":[]})", "", OB_INVALID_ARGUMENT);
  render("long repeated replacement", "{\"template\":\"{0}{0}{0}\",\"args\":[\"" + std::string(100000, 'x') + "\"]}", std::string(300000, 'x'));
  std::printf("TOTAL %d checks, %d failures\n", checks, failures);
  return failures ? 1 : 0;
}
