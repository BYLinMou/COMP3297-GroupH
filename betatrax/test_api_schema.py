from django.test import TestCase
from drf_spectacular.generators import SchemaGenerator


class ApiSchemaDocumentationTests(TestCase):
    def test_schema_documents_core_endpoints_with_concrete_responses(self):
        schema = SchemaGenerator(urlconf="betatrax.urls").get_schema(request=None, public=True)
        paths = schema["paths"]

        expected_operation_ids = {
            "/api/defects/": ("get", "listDefects"),
            "/api/defects/new/": ("post", "submitDefect"),
            "/api/defects/{defect_id}/": ("get", "getDefectDetail"),
            "/api/defects/{defect_id}/actions/": ("post", "applyDefectAction"),
            "/api/products/register/": ("post", "registerProduct"),
            "/api/tenants/register/": ("post", "registerTenant"),
            "/api/developers/{developer_id}/effectiveness/": ("get", "getDeveloperEffectiveness"),
        }
        for path, (method, operation_id) in expected_operation_ids.items():
            with self.subTest(path=path):
                self.assertEqual(paths[path][method]["operationId"], operation_id)

        self.assertEqual(
            paths["/api/defects/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/DefectListResponse",
        )
        self.assertEqual(
            paths["/api/defects/{defect_id}/actions/"]["post"]["requestBody"]["content"]["application/json"][
                "schema"
            ]["$ref"],
            "#/components/schemas/DefectActionRequestDoc",
        )

        action_values = schema["components"]["schemas"]["ActionEnum"]["enum"]
        for action in ("accept_open", "reject", "duplicate", "cannot_reproduce", "reopen", "add_comment"):
            self.assertIn(action, action_values)

    def test_schema_documents_swagger_auth_for_protected_endpoints(self):
        schema = SchemaGenerator(urlconf="betatrax.urls").get_schema(request=None, public=True)
        security_schemes = schema["components"]["securitySchemes"]

        self.assertEqual(security_schemes["basicAuth"]["type"], "http")
        self.assertEqual(security_schemes["basicAuth"]["scheme"], "basic")
        self.assertEqual(security_schemes["cookieAuth"]["in"], "cookie")
        self.assertIn("Authorize", schema["info"]["description"])

        protected_operations = (
            schema["paths"]["/api/defects/"]["get"],
            schema["paths"]["/api/defects/{defect_id}/"]["get"],
            schema["paths"]["/api/defects/{defect_id}/actions/"]["post"],
            schema["paths"]["/api/products/register/"]["post"],
            schema["paths"]["/api/tenants/register/"]["post"],
            schema["paths"]["/api/developers/{developer_id}/effectiveness/"]["get"],
        )
        for operation in protected_operations:
            with self.subTest(operation=operation["operationId"]):
                self.assertIn({"basicAuth": []}, operation["security"])
                self.assertIn("Authorize", operation["description"])
