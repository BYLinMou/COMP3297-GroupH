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
        self.assertEqual(
            paths["/api/defects/new/"]["post"]["responses"]["400"]["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/DefectCreateBadRequestResponse",
        )

        action_values = schema["components"]["schemas"]["ActionEnum"]["enum"]
        for action in ("accept_open", "reject", "duplicate", "cannot_reproduce", "reopen", "add_comment"):
            self.assertIn(action, action_values)

    def test_schema_descriptions_and_examples_support_manual_testing(self):
        schema = SchemaGenerator(urlconf="betatrax.urls").get_schema(request=None, public=True)
        paths = schema["paths"]

        action_operation = paths["/api/defects/{defect_id}/actions/"]["post"]
        tenant_operation = paths["/api/tenants/register/"]["post"]
        product_operation = paths["/api/products/register/"]["post"]
        defect_create_operation = paths["/api/defects/new/"]["post"]

        self.assertEqual(action_operation["summary"], "Apply workflow action to a defect")
        self.assertIn("Action-specific payload rules", action_operation["description"])
        self.assertIn("starter templates", action_operation["description"])
        self.assertIn("examples", action_operation["requestBody"]["content"]["application/json"])
        action_examples = action_operation["requestBody"]["content"]["application/json"]["examples"]
        for example_key in (
            "AcceptAndOpen",
            "Reject",
            "MarkDuplicate",
            "TakeOwnership",
            "SetFixed",
            "CannotReproduce",
            "SetResolved",
            "Reopen",
            "AddComment",
        ):
            with self.subTest(example_key=example_key):
                self.assertIn(example_key, action_examples)

        self.assertEqual(tenant_operation["summary"], "Register tenant from public schema")
        self.assertIn("starter template", tenant_operation["description"])
        self.assertIn("examples", tenant_operation["requestBody"]["content"]["application/json"])

        self.assertEqual(product_operation["summary"], "Register product in current tenant")
        self.assertIn("starter template", product_operation["description"])
        self.assertIn("examples", product_operation["requestBody"]["content"]["application/json"])

        self.assertEqual(defect_create_operation["summary"], "Submit defect")
        self.assertIn("starter template", defect_create_operation["description"])
        self.assertIn("examples", defect_create_operation["requestBody"]["content"]["application/json"])

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

    def test_schema_documents_authentication_failure_shape_for_protected_endpoints(self):
        schema = SchemaGenerator(urlconf="betatrax.urls").get_schema(request=None, public=True)
        paths = schema["paths"]

        protected_paths = (
            ("/api/defects/", "get"),
            ("/api/defects/{defect_id}/", "get"),
            ("/api/defects/{defect_id}/actions/", "post"),
            ("/api/products/register/", "post"),
            ("/api/tenants/register/", "post"),
            ("/api/developers/{developer_id}/effectiveness/", "get"),
        )
        for path, method in protected_paths:
            with self.subTest(path=path, method=method):
                self.assertEqual(
                    paths[path][method]["responses"]["403"]["content"]["application/json"]["schema"]["$ref"],
                    "#/components/schemas/AuthenticationErrorResponse",
                )
