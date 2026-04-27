# Test Case Inventory

This document lists the concrete automated test cases currently implemented in the repository, grouped by execution mode and test file.

## Execution Modes

### Non-tenant mode

- `ENABLE_DJANGO_TENANTS=False`
- SQLite database
- Primary files:
  - `defects/testsuite/test_effectiveness.py`
  - `defects/testsuite/test_services.py`
  - `defects/testsuite/test_api_client.py`
  - `defects/testsuite/test_views_request_factory.py`
  - `frontend/tests.py`
  - `tenancy/tests.py`
  - `betatrax/tests.py`
  - `betatrax/test_api_schema.py`

### Tenant mode

- `ENABLE_DJANGO_TENANTS=True`
- PostgreSQL + `django-tenants`
- Primary file:
  - `tenancy/test_tenant_mode_integration.py`

## Shared Baseline Data

Several defect API tests inherit from `defects.testsuite.base.DefectApiTestCase`. Unless overridden, they start with:

- owner user: `owner-001`
- developer user: `dev-001`
- product: `Prod_1`
- seed defect:
  - `report_id="BT-RP-1002"`
  - `status="New"`
  - `version="0.9.0"`
  - `title="Poor readability in dark mode"`

## Non-tenant Mode Test Cases

### 1. `defects/testsuite/test_effectiveness.py`

Tests for `defects.effectiveness.classify_developer(fixed, reopened)`.

1. `test_fixed_less_than_20_returns_insufficient_data`
   - Input: `(19, 0)`
   - Expected: `"Insufficient data"`
2. `test_ratio_below_1_over_32_returns_good`
   - Input: `(32, 0)`
   - Expected: `"Good"`
3. `test_ratio_between_1_over_32_and_1_over_8_returns_fair`
   - Input: `(32, 1)`
   - Ratio: `1/32`
   - Expected: `"Fair"`
4. `test_ratio_greater_or_equal_1_over_8_returns_poor`
   - Input: `(24, 3)`
   - Ratio: `1/8`
   - Expected: `"Poor"`
5. `test_negative_input_raises_value_error`
   - Input: `(-1, 0)`
   - Expected: raises `ValueError`

### 2. `defects/testsuite/test_services.py`

Direct service/unit tests.

#### Signal and seed helpers

1. `test_seed_signal_ignores_non_defects_sender`
   - Sender: `name="auth"`
   - Expected: no demo seed call
2. `test_seed_signal_skips_public_schema_in_tenant_mode`
   - Mode override: `USE_DJANGO_TENANTS=True`
   - Mock public schema context
   - Expected: no demo seed call
3. `test_seed_signal_runs_when_defect_tables_exist`
   - Sender: `name="defects"`
   - Expected: `ensure_demo_seed()` called once
4. `test_seed_signal_skips_when_tables_are_not_ready`
   - Mock no tables / `ProgrammingError`
   - Expected: defect tables reported unavailable

#### Defect creation and identifiers

5. `test_create_defect_creates_initial_history_record`
   - Input defect:
     - product=`Prod_1`
     - version=`1.2.3`
     - title=`Autosave issue`
     - tester=`tester-002`
     - email=`tester2@example.com`
   - Expected:
     - initial history exists
     - `from_status="New"`
     - `to_status="New"`
     - `actor_id="tester-002"`
6. `test_next_report_id_skips_invalid_report_identifiers`
   - Existing invalid `report_id="LEGACY-ID"`
   - Expected next id: `BT-RP-2402`

#### Status transitions and notifications

7. `test_accept_open_sends_status_email_and_updates_history`
   - Start: defect `BT-RP-2401`, status `New`
   - Action: `accept_open`
   - Payload: `severity="High"`, `priority="P1"`
   - Actor: owner `owner-001`
   - Expected:
     - message `Defect accepted and moved to Open.`
     - defect status `Open`
     - 1 email sent
     - latest history `to_status="Open"`
8. `test_add_comment_persists_comment_record`
   - Action: `add_comment`
   - Comment: `Need more logs`
   - Expected comment row created with `author_id="owner-001"`
9. `test_accept_open_validates_permissions_and_inputs`
   - Cases:
     - developer actor attempts accept -> error
     - wrong owner actor attempts accept -> error
     - severity `Critical` -> error
     - priority `P9` -> error
     - status already `Open` -> error
10. `test_reject_duplicate_and_comment_guard_rails`
    - Reject on `Open` defect -> error
    - Reject by developer -> error
    - Reject by wrong owner -> error
    - Duplicate self-reference:
      - `duplicate_of` = same report id
      - Expected status `Duplicate`, but `duplicate_of=None`
    - Duplicate by developer -> error
    - Duplicate by wrong owner -> error
    - Duplicate when status `Open` -> error
    - Comment by outsider actor -> error
11. `test_take_fix_cannot_reproduce_resolve_and_reopen_guard_rails`
    - `take_ownership` on `New` -> error
    - `take_ownership` by owner on `Open` -> error
    - `set_fixed` by unassigned developer -> error
    - `set_fixed` by owner -> error
    - `cannot_reproduce` on `Open` -> error
    - `cannot_reproduce` by owner -> error
    - `cannot_reproduce` by wrong developer -> error
    - `set_resolved` on `Open` -> error
    - `set_resolved` by developer -> error
    - `set_resolved` by wrong owner -> error
    - `reopen` on `Open` -> error
    - `reopen` by developer -> error
    - `reopen` by wrong owner -> error
12. `test_unknown_action_and_register_product_validation_paths`
    - Unknown action `unsupported` -> error

#### Product registration

13. `test_register_product_rejects_duplicate_developer_assignment`
    - Existing assignment: `dev-001` already bound to `Prod_1`
    - New request:
      - owner=`owner-002`
      - product=`Prod_2`
      - developers=`["dev-001"]`
    - Expected: `ValidationError`
14. `test_unknown_action_and_register_product_validation_paths`
    - Register product invalid cases:
      - blank owner username
      - blank `product_id`
      - blank `name`
      - `developers` not list (`"dev-002"`)
      - blank developer id (`"   "`)
      - missing developer account (`"missing-dev"`)
    - Valid case:
      - owner=`owner-010`
      - product=`Prod_10`
      - developers=`None`
      - Expected product created with no developer rows
    - Duplicate `product_id="Prod_10"` by another owner -> error
    - Duplicate developer ids list `[dev-002, dev-002]`
      - Expected only one `ProductDeveloper` row

#### Auth / model helpers

15. `test_actor_from_user_handles_anonymous_and_group_membership`
    - Anonymous user -> empty actor id, no owner/developer flags
    - Owner user `owner-002` -> owner flag true
16. `test_model_string_representations_are_human_readable`
    - `str(Product)` -> `Prod_1`
    - `str(ProductDeveloper)` -> `dev-001@Prod_1`
    - `str(DefectReport)` -> `BT-RP-2401`
    - `str(Tenant)` -> `tenant_a (tenant-a.example.com)`

#### Demo data cleanup helpers

17. `test_demo_helpers_create_seed_users_and_remove_legacy_records`
    - Legacy product: `PRD-1007`
    - Legacy defect: `BT-RP-2471`
    - Expected:
      - users `owner-001`, `dev-001`, `dev-004` exist
      - legacy product and defect removed
18. `test_demo_helpers_remove_stale_reports_not_linked_to_legacy_product`
    - Stale defect: `BT-RP-2476`
    - Expected removed
19. `test_demo_dt_supports_iso_strings_with_or_without_timezone`
    - Input: `2026-04-24T12:30:00+08:00`
    - Fallback input: `2026-04-24T12:30:00`
    - Expected timezone-aware datetime in both cases
20. `test_record_status_change_skips_same_status_transition`
    - `from_status="New"`, `to_status="New"`
    - Expected: history count unchanged

#### Duplicate chain notifications

21. `test_root_status_change_notifies_duplicate_chain`
    - Root defect has tester email `tester@example.com`
    - Child duplicate:
      - `report_id="BT-RP-2405"`
      - email=`duplicate@example.com`
      - `duplicate_of=root`
    - Root action: `accept_open`
    - Expected:
      - 2 emails
      - recipients `duplicate@example.com`, `tester@example.com`
22. `test_non_root_transition_does_not_broadcast_to_other_duplicates`
    - Root: `BT-RP-2410`
    - Child: `BT-RP-2411`
    - Sibling: `BT-RP-2412`
    - Child action: `duplicate` with `duplicate_of=root`
    - Expected: only 1 email to child tester
23. `test_iter_duplicate_descendants_ignores_seen_nodes_in_cycles`
    - Create cycle between `BT-RP-2401` and `BT-RP-2414`
    - Expected descendants list only contains `BT-RP-2414`
24. `test_root_status_change_skips_duplicate_without_email`
    - Child duplicate has blank email
    - Root action: `accept_open`
    - Expected: only root tester email sent

#### Tenant service and effectiveness summary

25. `test_register_tenant_validates_and_persists`
    - Invalid cases:
      - blank schema
      - reserved schema `public`
      - invalid schema `1team`
      - blank domain
      - invalid domain `invalid_domain`
    - Valid case:
      - `schema_name="team_a"`
      - `domain="team-a.example.com"`
      - `name="Team A"`
      - Expected tenant + primary domain created
    - Duplicate schema / duplicate domain -> error
26. `test_summarize_developer_effectiveness_requires_owner_team_membership`
    - Input: owner `owner-001`, developer `dev-404`
    - Expected `ValidationError`
27. `test_summarize_developer_effectiveness_validates_required_inputs`
    - Blank owner id -> error
    - Blank developer id -> error
28. `test_summarize_developer_effectiveness_returns_counts`
    - Defect flow:
      - `New -> Open -> Assigned -> Fixed -> Reopened`
    - Expected summary:
      - `developer_id="dev-001"`
      - `fixed=1`
      - `reopened=1`
      - classification `Insufficient data`

### 3. `defects/testsuite/test_api_client.py`

API endpoint tests using `APITestCase` and `APIClient`.

#### Defect submission

1. `test_submit_defect_invalid_email_returns_serializer_error`
   - POST `/api/defects/new/`
   - Input email: `not-an-email`
   - Expected: `400`, response contains `email`
2. `test_submit_defect_missing_required_fields_returns_400`
   - Input only `product_id="Prod_1"`
   - Expected:
     - `400`
     - error `Missing required fields.`
     - missing fields include `title`
3. `test_submit_defect_unknown_product_returns_404`
   - Input `product_id="PRD-UNKNOWN"`
   - Expected: `404`, `Unknown Product ID.`
4. `test_submit_defect_success_stored_as_new`
   - Valid defect created with no email
   - Expected:
     - `201`
     - DB defect status `New`
     - `tester_email=""`

#### Listing and detail permissions

5. `test_list_requires_authentication`
   - Anonymous GET `/api/defects/?status=Open`
   - Expected: `403`
6. `test_list_open_defects_for_developer`
   - First move seed defect to `Open`
   - Developer query:
     - `status=Open`
     - `developer_id=dev-001`
   - Expected: `200`, at least one `Open` item
7. `test_owner_can_filter_list_by_slug_and_spaced_status_values`
   - Create defect and move to `Cannot Reproduce`
   - Owner query:
     - `status=cannot-reproduce`
   - Expected: `200`, created defect appears
   - Owner query:
     - `status=Cannot Reproduce`
   - Expected: `200`, created defect appears
8. `test_developer_can_filter_reopened_with_slug_status_value`
   - Create defect and move to `Reopened`
   - Developer query:
     - `status=reopened`
     - `developer_id=dev-001`
   - Expected: `200`, created defect appears
9. `test_list_rejects_authenticated_user_without_role`
   - User: `viewer-001`
   - Expected: `403`
10. `test_list_enforces_owner_and_developer_query_scope`
   - Owner with `owner_id=owner-999` -> `403`
   - Developer with `developer_id=dev-999` -> `403`
11. `test_list_allows_matching_owner_and_developer_scope_filters`
   - Seed defect set to `Open`
   - Owner with `owner_id=owner-001` -> `200`, 1 item
   - Developer with `developer_id=dev-001` -> `200`, 1 item
12. `test_owner_can_filter_list_by_product`
    - Add second product `Prod_2` and defect `BT-RP-2000`
    - Owner filters `product_id=Prod_1`
    - Expected: only 1 visible item
13. `test_owner_can_get_defect_detail`
    - Owner GET seed defect detail
    - Expected: `200`, includes `description` and `steps`
14. `test_developer_cannot_get_new_defect_detail`
    - Developer GET seed defect in `New`
    - Expected: `403`
15. `test_detail_returns_404_for_unknown_or_out_of_scope_defect`
    - Unknown id `BT-RP-9999` -> `404`
    - Other owner's defect `BT-RP-3000` -> `404`
16. `test_developer_without_team_membership_cannot_get_detail`
    - Outsider developer `dev-404`, defect set to `Open`
    - Expected: `404`
17. `test_developer_can_get_open_defect_detail_for_assigned_product`
    - Seed defect set to `Open`
    - Expected: developer gets `200`
18. `test_developer_cannot_list_new`
    - Developer query `status=New`
    - Expected: `403`

#### Lifecycle and action endpoints

19. `test_take_ownership_requires_team_membership`
    - Open defect + outsider developer `dev-999`
    - Expected: `400`, product team error
20. `test_lifecycle_open_to_assigned_to_fixed_to_resolved`
    - Sequence:
      - owner `accept_open`
      - developer `take_ownership`
      - developer `set_fixed` with `fix_note="patched"`
      - owner `set_resolved` with `retest_note="verified"`
    - Expected statuses:
      - `Open`
      - `Assigned`
      - `Fixed`
      - `Resolved`
21. `test_owner_can_reject_new_defect`
    - New defect title `reject-flow`
    - Action `reject`
    - Expected status `Rejected`
22. `test_owner_can_mark_duplicate_with_reference`
    - Target defect + duplicate defect
    - Action:
      - `duplicate`
      - `duplicate_of=target_id`
    - Expected:
      - status `Duplicate`
      - DB link set
23. `test_duplicate_requires_existing_target`
    - `duplicate_of="BT-RP-999999"`
    - Expected: `400`
24. `test_owner_can_mark_duplicate_with_blank_reference`
    - Action:
      - `duplicate`
      - `duplicate_of=""`
    - Expected:
      - response `200`
      - status `Duplicate`
      - DB `duplicate_of` stays null
25. `test_assigned_developer_can_mark_cannot_reproduce`
    - Move defect to `Assigned`
    - Action:
      - `cannot_reproduce`
      - `fix_note="cannot repro locally"`
    - Expected status `Cannot Reproduce`
26. `test_owner_can_reopen_fixed_defect`
    - Move defect to `Fixed`
    - Action:
      - `reopen`
      - `retest_note="still failing"`
    - Expected status `Reopened`
27. `test_action_endpoint_rejects_invalid_actor_or_state_transitions`
    - Developer tries `reject` on `New` defect -> `400`
    - Owner tries `set_resolved` while defect is `Open` -> `400`
    - Wrong developer `dev-002` tries `set_fixed` on defect assigned to `dev-001` -> `400`
28. `test_owner_can_add_comment_and_empty_comment_is_rejected`
    - Valid comment:
      - `Need more repro info`
      - Expected message `Comment added.`
    - Blank comment `"   "` -> `400`
29. `test_action_returns_404_and_serializer_errors`
    - Missing defect id `BT-RP-9999` -> `404`
    - Missing `action` field -> `400`

#### Product, tenant, effectiveness endpoints

30. `test_product_owner_can_register_product`
    - Owner `owner-002`
    - Developer `dev-777`
    - Payload:
      - `product_id="Prod_2"`
      - `name="New Product"`
      - `developers=["dev-777"]`
    - Expected: `201`, product + developer assignment created
31. `test_owner_with_existing_product_cannot_register_again`
    - Existing owner `owner-001`
    - Payload `product_id="Prod_3"`
    - Expected: `400`
32. `test_developer_cannot_register_product`
    - Developer attempts product registration
    - Expected: `403`
33. `test_register_product_returns_validation_error_detail`
    - Developers payload is string `"dev-001"` instead of list
    - Expected: `400`
34. `test_register_product_rejects_blank_fields_and_unknown_or_assigned_developers`
    - Blank `product_id` -> `400`
    - Blank `name` -> `400`
    - Blank developer id `"   "` -> `400`
    - Missing developer `missing-dev` -> `400`
    - Already-assigned developer `dev-001` -> `400`
35. `test_platform_admin_can_register_tenant`
    - Superuser `platform-admin`
    - Valid tenant:
      - `schema_name="team_blue"`
      - `domain="team-blue.example.com"`
      - `name="Team Blue"`
    - Expected: `201`
    - Duplicate schema `team_blue` with new domain -> `400`
36. `test_platform_admin_register_tenant_requires_serializer_fields`
    - Missing `schema_name`
    - Expected: `400`
37. `test_non_platform_admin_cannot_register_tenant`
    - Owner attempts tenant registration
    - Expected: `403`
38. `test_product_owner_can_query_developer_effectiveness`
    - Create one defect and move to `Fixed`
    - Owner GET effectiveness for `dev-001`
    - Expected:
      - `fixed=1`
      - `reopened=0`
      - classification `Insufficient data`
39. `test_product_owner_can_query_effectiveness_good_fair_and_poor`
    - Separate owner/developer/product datasets:
      - `Good`: `fixed=20`, `reopened=0`
      - `Fair`: `fixed=32`, `reopened=1`, `reopen_ratio=1/32`
      - `Poor`: `fixed=24`, `reopened=3`, `reopen_ratio=3/24`
    - Expected endpoint classifications:
      - `Good`
      - `Fair`
      - `Poor`
40. `test_developer_cannot_query_effectiveness`
    - Developer queries own effectiveness endpoint
    - Expected: `403`
41. `test_effectiveness_rejects_non_team_developer`
    - Query `dev-999`
    - Expected: `400`

### 4. `defects/testsuite/test_views_request_factory.py`

Direct view tests using `APIRequestFactory`.

1. `test_list_view_filters_to_authenticated_owner_product_scope`
   - Owner request to list view
   - Expected: `200`, one item, report id `BT-RP-1002`
2. `test_action_view_returns_403_for_anonymous_request`
   - Anonymous POST reject action
   - Expected: `403`
3. `test_detail_view_rejects_non_role_user_and_unknown_defect`
   - Viewer requests seed defect -> `403`
   - Owner requests `BT-RP-9999` -> `404`
4. `test_detail_view_hides_out_of_scope_owner_and_new_status_for_developer`
   - Other owner requests seed defect -> `404`
   - Developer requests `New` defect -> `403`
5. `test_action_view_rejects_authenticated_user_with_blank_actor_id`
   - Username is whitespace `"   "`
   - Action reject
   - Expected: `403`
6. `test_tenant_register_view_denies_non_platform_admin`
   - Owner POST tenant registration
   - Expected: `403`
7. `test_effectiveness_view_denies_non_owner_actor`
   - Developer requests effectiveness view
   - Expected: `403`

### 5. `frontend/tests.py`

Frontend smoke/integration tests.

1. `test_login_page_renders`
   - GET login page
   - Expected: `200`
2. `test_external_auth_rejects_invalid_credentials_and_accepts_valid_login`
   - Bad password for `owner-001` -> page contains `Invalid username or password.`
   - Correct password -> `302` redirect to home
3. `test_sign_out_clears_session`
   - Logged-in owner signs out
   - Expected redirect to auth page
4. `test_owner_home_page_lists_visible_defects`
   - Owner home page shows `BT-RP-1002`
5. `test_home_redirects_non_role_user_and_filters_statuses`
   - Viewer hitting home -> redirect
   - Developer filtering `status=open` after seed defect set to `Open` -> defect visible
   - Developer filtering `status=new` -> defect hidden
   - Developer filtering `status=unknown` -> defect hidden
6. `test_developer_cannot_open_new_defect_detail_page`
   - Developer GET new defect detail page
   - Expected `404`
7. `test_register_product_page_renders_and_non_owner_is_redirected`
   - Owner GET register product page -> `200`, page includes `Register Product` and `dev-001`
   - Developer GET same page -> redirected home
8. `test_register_product_page_handles_missing_developer_group`
   - Delete developer group
   - Owner GET page
   - Expected text `No developer accounts found.`
9. `test_owner_can_register_product_and_invalid_submission_is_redisplayed`
   - Owner `owner-002`, developer `dev-002`
   - Invalid post with `developers=["missing-dev"]` -> page redisplays with error
   - Valid post with `product_id="Prod_2"` -> redirect home, product/assignment created
10. `test_create_defect_page_enforces_role_and_validates_submission`
    - Developer GET create page -> redirect home
    - Owner GET create page -> `200`, page includes `Create New Defect`
    - Missing fields post -> redirect back to create page
    - Unknown product `Prod_404` -> redirect back
    - Valid post:
      - title `Created from UI`
      - email `tester2@example.com`
      - Expected redirect to created defect detail page
11. `test_defect_detail_supports_comments_actions_and_scope_checks`
    - Owner GET detail -> page contains `No comments yet.`
    - Owner POST comment `Need more detail` -> comment row created
    - Invalid action `set_fixed` too early -> redirect
    - Other owner GET same detail -> `404`
    - Roleless viewer GET same detail -> redirect auth
12. `test_defect_detail_returns_404_for_missing_or_unassigned_developer_scope`
    - Missing defect id `BT-RP-9999` -> `404`
    - Outsider developer `dev-404` requests open defect -> `404`

### 6. `tenancy/tests.py`

Non-tenant and mixed tenant-logic tests.

#### Admin visibility

1. `test_tenant_admin_is_visible_outside_tenant_mode`
   - `USE_DJANGO_TENANTS=False`
   - Expected tenant/domain admin permissions true
2. `test_tenant_admin_is_hidden_inside_tenant_schema`
   - `USE_DJANGO_TENANTS=True`
   - Request tenant schema `local`
   - Expected tenant/domain admin permissions false
3. `test_tenant_admin_is_visible_in_public_schema`
   - `USE_DJANGO_TENANTS=True`
   - Request tenant schema `public`
   - Expected tenant admin module visible
4. `test_tenant_scoped_admin_is_visible_outside_tenant_mode`
   - `USE_DJANGO_TENANTS=False`
   - Product admin permissions true
5. `test_tenant_scoped_admin_is_hidden_in_public_schema`
   - `USE_DJANGO_TENANTS=True`
   - schema `public`
   - Product admin permissions false
6. `test_tenant_scoped_admin_is_visible_inside_tenant_schema`
   - `USE_DJANGO_TENANTS=True`
   - schema `local`
   - Product admin module visible

#### Tenant registration guards and schema utilities

7. `test_register_tenant_api_is_not_available_inside_tenant_schema`
   - `USE_DJANGO_TENANTS=True`
   - POST tenant registration from schema `local`
   - Payload:
     - `schema_name="team_x"`
     - `domain="team-x.example.com"`
   - Expected: `404`, mentions public schema
8. `test_missing_request_tenant_uses_connection_schema_fallback`
   - Mock connection schema `local`
   - Expected `is_public_schema_context()` returns false

#### Middleware behavior

9. `test_configured_public_domain_uses_public_urlconf`
   - Host `platform.localhost`
   - `PUBLIC_SCHEMA_DOMAINS=["platform.localhost"]`
   - Expected `request.urlconf="betatrax.public_urls"`
10. `test_unconfigured_missing_tenant_host_raises_404`
    - Host `unknown.localhost`
    - Expected `Http404`
11. `test_without_public_domains_uses_standard_public_fallback`
    - Host `missing.localhost`
    - No configured public domains but `SHOW_PUBLIC_IF_NO_TENANT_FOUND=True`
    - Expected public urlconf fallback

#### Tenant domain and admin user services

12. `test_add_tenant_domain_validates_and_persists`
    - Existing tenant:
      - `schema_name="team_a"`
      - `domain="team-a.example.com"`
    - Invalid domain `""` -> error
    - Invalid domain `"invalid_domain"` -> error
    - Existing domain `"team-a.example.com"` -> error
    - Valid domain `"app.team-a.example.com"` with `is_primary=True` -> created
    - Duplicate `"app.team-a.example.com"` -> error
13. `test_create_tenant_admin_user_validates_and_persists_staff_user`
    - Blank username -> error
    - Blank password -> error
    - Valid user:
      - username `tenant-admin`
      - email `tenant-admin@example.com`
      - password `Pass1234!`
      - Expected staff/superuser true
    - Duplicate username -> error
14. `test_create_tenant_admin_user_uses_schema_context_in_tenant_mode`
    - `USE_DJANGO_TENANTS=True`
    - Mock `schema_context`
    - Expected called with `"team_a"`
15. `test_create_tenant_admin_user_falls_back_when_schema_context_unavailable`
    - `USE_DJANGO_TENANTS=True`
    - Patch `schema_context=None`
    - Expected user `fallback-admin` created

#### Platform tenant console

16. `test_platform_home_redirects_to_tenant_console`
    - GET platform home
    - Expected redirect to tenant console
17. `test_tenant_console_requires_login`
    - Anonymous GET tenant console
    - Expected redirect to `/platform/login/`
18. `test_tenant_console_denies_non_platform_admin`
    - Viewer logged in
    - Expected `403`
19. `test_tenant_console_denies_tenant_schema_context`
    - `USE_DJANGO_TENANTS=True`, schema `local`
    - Expected `PermissionDenied`
20. `test_tenant_console_lists_public_domains_and_tenants`
    - Existing tenant `team_a`
    - Expected page contains `Tenant Console`, `platform.localhost`, `team_a`
21. `test_tenant_console_creates_tenant_and_adds_domain`
    - Create tenant:
      - `schema_name="team_blue"`
      - `domain="team-blue.example.com"`
      - `name="Team Blue"`
      - admin username `team-blue-admin`
      - admin email `team-blue-admin@example.com`
      - admin password `Pass1234!`
    - Expected:
      - redirect
      - tenant and domain created
      - admin user exists and is staff/superuser
    - Add domain:
      - `domain="bugs.team-blue.example.com"`
      - `is_primary=on`
      - Expected domain row created
22. `test_tenant_console_handles_invalid_posts`
    - Unknown action `bad` -> page shows `Unknown platform action.`
    - Missing tenant admin username -> error
    - Missing tenant admin password -> error
    - Invalid create with blank schema + invalid domain -> error
    - Missing tenant id `9999` for add domain -> error
    - Invalid domain `"invalid"` for existing tenant `team_red` -> error
23. `test_platform_login_handles_authentication_paths`
    - GET login page -> page contains `Tenant administration`
    - Platform user bad password -> error
    - Viewer valid password -> `Only platform admins`
    - Platform user valid login with `next=<console>` -> redirect
    - Already authenticated platform admin GET login -> redirect to console
24. `test_platform_logout_clears_session`
    - Logged-in admin GET logout
    - Expected page contains `Signed out.` and `Sign In`

### 7. `betatrax/tests.py`

Settings/database parsing tests.

1. `test_postgresql_database_url_builds_django_config`
   - URL:
     - `postgresql://db_user:p%40ss@db.local:15432/betatrax?sslmode=require`
   - Expected:
     - engine `postgresql`
     - user `db_user`
     - password `p@ss`
     - host `db.local`
     - port `15432`
     - options `{"sslmode": "require"}`
2. `test_sqlite_database_url_builds_django_config`
   - URL `sqlite:///./data/db.sqlite3` -> `./data/db.sqlite3`
   - URL `sqlite:///db.sqlite3` -> `db.sqlite3`
   - URL `sqlite:////data/db.sqlite3` -> `/data/db.sqlite3`
   - URL `sqlite:///:memory:` -> `:memory:`
3. `test_database_url_validation_errors_are_explicit`
   - Invalid cases:
     - `mysql://user:pass@localhost/betatrax`
     - `postgresql://localhost`
     - `postgresql://localhost:bad/betatrax`
     - `sqlite://localhost/db.sqlite3`
     - `sqlite://`
   - Expected: `ImproperlyConfigured`
4. `test_database_url_takes_precedence_over_legacy_variables`
   - Env contains both `DATABASE_URL` and legacy vars
   - Expected `DATABASE_URL` wins
5. `test_legacy_postgres_variables_still_work_without_database_url`
   - Env contains only legacy postgres vars
   - Expected parsed postgres config

### 8. `betatrax/test_api_schema.py`

OpenAPI documentation tests.

1. `test_schema_documents_core_endpoints_with_concrete_responses`
   - Generates schema from `betatrax.urls`
   - Expected operation IDs:
     - `/api/defects/` -> `listDefects`
     - `/api/defects/new/` -> `submitDefect`
     - `/api/defects/{defect_id}/` -> `getDefectDetail`
     - `/api/defects/{defect_id}/actions/` -> `applyDefectAction`
     - `/api/products/register/` -> `registerProduct`
     - `/api/tenants/register/` -> `registerTenant`
     - `/api/developers/{developer_id}/effectiveness/` -> `getDeveloperEffectiveness`
   - Also checks:
     - list response schema ref `#/components/schemas/DefectListResponse`
     - action request schema ref `#/components/schemas/DefectActionRequestDoc`
     - action enum contains `accept_open`, `reject`, `duplicate`, `cannot_reproduce`, `reopen`, `add_comment`
2. `test_schema_documents_swagger_auth_for_protected_endpoints`
   - Expected schema includes:
     - `basicAuth`
     - `cookieAuth`
   - Protected operations must declare auth requirements and mention `Authorize`

## Tenant Mode Test Cases

### `tenancy/test_tenant_mode_integration.py`

These tests only run when:

- `ENABLE_DJANGO_TENANTS=True`
- PostgreSQL is available

1. `test_tenant_host_can_create_and_list_defects_inside_tenant_schema`
   - Tenant schema name: `tenant_test`
   - Tenant host: `tenant.test.com`
   - Owner user: `tenant-owner`
   - Developer user: `tenant-dev`
   - Product: `TenantProd`
   - Create defect payload:
     - `product_id="TenantProd"`
     - `version="2.0.0"`
     - `title="Tenant scoped bug"`
     - `description="Tenant-only defect"`
     - `steps="Open tenant app"`
     - `tester_id="tenant-tester"`
   - Expected:
     - POST returns `201`
     - created defect exists with status `New`
     - authenticated owner GET list on same host returns `200`
     - created `report_id` appears in list
2. `test_tenant_lifecycle_actions_work_inside_tenant_schema`
   - Create defect:
     - title `Tenant lifecycle defect`
     - tester `tenant-lifecycle`
   - Sequence on `tenant.test.com`:
     - owner `accept_open`
     - developer `take_ownership`
     - developer `set_fixed` with `fix_note="tenant patch applied"`
     - owner `reopen` with `retest_note="still reproducible in tenant env"`
   - Expected:
     - final status `Reopened`
     - `assignee_id="tenant-dev"`
     - history count `5`
3. `test_tenant_developer_cannot_view_new_defect_detail`
   - Create defect:
     - title `Tenant new detail`
     - tester `tenant-detail`
   - Developer GET detail on `tenant.test.com`
   - Expected:
     - response `403`
     - error contains `cannot access New`
4. `test_tenant_owner_can_query_developer_effectiveness`
   - Create 20 tenant-scoped defects
   - For each:
     - owner `accept_open`
     - developer `take_ownership`
     - developer `set_fixed`
   - Owner GET `/api/developers/tenant-dev/effectiveness/`
   - Expected:
     - `fixed=20`
     - `reopened=0`
     - classification `Good`
5. `test_tenant_models_exist_in_tenant_schema_not_public_schema`
   - In tenant schema:
     - table `defects_product` must exist
   - In public schema:
     - table `defects_product` must not exist
6. `test_public_schema_can_register_tenant`
   - Public schema user:
     - username `platform-api-admin`
     - group `platform_admin`
   - Payload:
     - `schema_name="api_team"`
     - `domain="api-team.test.com"`
     - `name="API Team"`
   - Expected:
     - response `201`
     - returned tenant schema name `api_team`

## Compatibility Entry Point

### `defects/tests.py`

This file does not define new cases. It re-exports:

- `defects.testsuite.test_api_client`
- `defects.testsuite.test_effectiveness`
- `defects.testsuite.test_services`
- `defects.testsuite.test_views_request_factory`

Its purpose is compatibility with CI commands importing `defects.tests` directly.

## Remaining Recommended Additions

### A. Broader tenant-mode endpoint coverage

Tenant mode now covers lifecycle, detail visibility, and effectiveness, but it still lacks:

1. Duplicate flow inside tenant schema
2. Reject flow inside tenant schema
3. Cannot-reproduce flow inside tenant schema
4. Tenant-mode list filter normalization (`cannot-reproduce`, `reopened`)

### B. More endpoint-level negative coverage

Useful remaining API assertions:

1. `accept_open` with invalid `severity`
2. `accept_open` with invalid `priority`
3. `cannot_reproduce` by non-assignee developer
4. `reopen` by wrong owner
5. `set_fixed` by owner through HTTP endpoint

### C. Tenant-mode notification and duplicate-chain behavior

These are covered in service tests but not yet under real tenant schema execution:

1. Root status change notifies duplicate chain
2. Non-root duplicate transition does not notify siblings
3. Duplicate without tester email is skipped
