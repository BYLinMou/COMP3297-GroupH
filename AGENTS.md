Continuosly define automation testing and test cases after each feature done.

After implementing code changes, update the documents (documents/*, README.md) tp describe new features usages if applicable. 

Track the .gitignore file and add all tmp files into it.

Commit after each core function done. Update the VERSION file as well for version control (jump number only when one core function done, or else change the alpha number, e.g. 0.0.0-alpha.1, 0.0.0-alpha.2)

In this project, we focus on developing backend API. You must complete backend API features and their test cases (make sure coverage 100% for both statements and branches). It is optional to update frontend template and test cases.

Run `conda activate betatrax` if you find packages missing.

---

Sprint3 sprint backlog:

Story ID	Task	Assigned To	Est. Hours	Actual Hours	Status
Sprint 3 — Carried over: Duplicate & Reject (US-07, US-08)					
US-07	Implement mark-duplicate action: prompt Product Owner to select root report, link records, update status		3		To Do
US-07	Send notification email on duplicate transition		1		To Do
US-08	Implement reject action: validate status 'New', update to 'Rejected', record timestamp		2		To Do
US-08	Send notification email on reject transition		1		To Do
Sprint 3 — Carried over: Cannot Reproduce (US-09)					
US-09	Implement cannot-reproduce action in apply_action service		1		To Do
US-09	Send notification email on cannot-reproduce transition		1		To Do
Sprint 3 — Carried over: Reopen (US-10)					
US-10	Implement reopen action: validate status 'Fixed', update to 'Reopened', store retest note		1		To Do
US-10	Send notification email on reopen transition		1		To Do
Sprint 3 — Carried over: Comments (US-11)					
US-11	Implement add-comment action: store text, date, author identity; reject empty text		2		To Do
Sprint 3 — Carried over: Duplicate email chain (US-12)					
US-12	Identify all duplicate-linked reports when root defect status changes		2		To Do
US-12	Send notification emails to testers of linked duplicate reports with stored email		1		To Do
Sprint 3 — Multi-tenancy (US-13, US-14)					
US-13	Install and configure django-tenants; add to INSTALLED_APPS and middleware		3		To Do
US-13	Switch database backend from SQLite to PostgreSQL; update settings		2		To Do
US-13	Implement Tenant model (schema_name, domain) and run migrations		2		To Do
US-13	Implement POST endpoint for tenant registration (Platform Admin only)		2		To Do
Sprint 3 — Developer effectiveness metric (US-15)					
US-15	Implement classify_developer(fixed, reopened) function with all four classification rules		2		To Do
US-15	Implement GET /api/developers/{id}/effectiveness/ endpoint		2		To Do
US-15	enforce Product Owner role check on the endpoint		1		To Do
Sprint 3 — Automated tests (US-16)					
US-16	Write one representative test per endpoint: submit defect, accept, take, fix, resolve		3		To Do
US-16	Write one representative test per endpoint: reject, duplicate, cannot reproduce, reopen, comment		3		To Do
US-16	Write one representative test per endpoint: register product, register tenant, developer metric		2		To Do
Sprint 3 — Coverage tests for effectiveness classification (US-17)					
US-17	Write test: F < 20 → 'Insufficient data'		1		To Do
US-17	Write test: R/F < 1/32 → 'Good'		1		To Do
US-17	Write test: 1/32 <= R/F < 1/8 → 'Fair'		1		To Do
US-17	Write test: R/F >= 1/8 → 'Poor'		1		To Do
US-17	Run coverage.py; confirm 100% statement and branch coverage on classification module		1		To Do
Sprint 3 — API documentation (US-18)					
US-18	Set up API documentation tooling (e.g. drf-spectacular)		2		To Do
US-18	Annotate all endpoints with schema descriptions, request/response examples		3		To Do
US-18	Review and remove auto-generated clutter; verify accuracy of all documented responses		1		To Do

---

Automated Testing Tutorial ppt:

Automated Testing
COMP3297 B/C 2025-2026
Overview
• Testing Python programs
• Unit Test
• Code coverage
• Testing APIs with Django REST Framework
• Unit Test
• Code coverage
• APIClient
• APIRequestFactory
2
Unit Testing
• Process of testing individual components in isolation.
• E.g. Individual functions, methods, object classes with several attributes and
methods
• Tests are calls to these components with different input parameters
• Test cases are a set of input and expected output that determine
whether a unit of code is working correctly
3
unittest - Unit testing framework in Python
• Kent Beck and Erich Gamma developed JUnit, a unit test framework
for Java, back in 1997
• Inspired by JUnit, unittest is developed for unit testing in Python
• unittest.py
• https://docs.python.org/3/library/unittest.html
4
unittest
• Testing Kit - Assert Methods in unittest
• More Details: https://docs.python.org/3/library/unittest.html#unittest.TestCase.debug
Method Checks that New in
assertEqual(a, b) a == b
assertNotEqual(a, b) a != b
assertTrue(x) bool(x) is True
assertFalse(x) bool(x) is False
assertIs(a, b) a is b 3.1
assertIsNot(a, b) a is not b 3.1
assertIsNone(x) x is None 3.1
assertIsNotNone(x) x is not None 3.1
assertIn(a, b) a in b 3.1
assertNotIn(a, b) a not in b 3.1
assertIsInstance(a, b) isinstance(a, b) 3.2
assertNotIsInstance(a, b) not isinstance(a, b) 3.2
5
Example 1 – Simple Unit Testing
6
Program output
Example 1 – Simple Unit Testing
Output (Testing result):
7
Tests are passed!
method name should start with test
Example 2 – Faulty Unit Testing
failed
failed
8
Example 2 – Faulty Unit Testing
Implementation error!
It should be n * n
Wrong test case!
Square root of 25 is 5
9
failed
failed
Example 3
-
Unit test with
Django
Recall the Domain Model from
Kevin’s tutorial
In orders/models.py:
10
Example 3 - Writing tests
11
The startapp command created
tests.py by default.
Be sure to use django.test.TestCase
rather than unittest.TestCase
Calls to __str__() in Product model
The test utility will find tests in any file named
test*.py under the current working directory
Tests will not use your production database.
Dummy databases are created for tests.
Example 3 - setUp()
• The setUp() allow you to define instructions that will be executed
before each test method. Refactor the previous code as below:
12
setUp() will be called once per test.
Thus, a new instance is created for
each individual test.
Example 3 - Continue to write more tests
13
Order model:
Example 3 - Continue to write more tests
14
OrderProduct model:
Example 3 - Running all tests
15
Code Coverage
• Code coverage measures the percentage of a particular program
entity that has been executed by all the test cases.
• Testing approaches
• Statement coverage (ensure every statement is executed at least once)
• Branch Coverage (ensure every branch (T, F) is executed at least once)
16
Python Implementation - Coverage.py
• Coverage.py
• A tool for measuring code coverage of Python programs
• Installation: pip install coverage
• https://pypi.org/project/coverage/
• Coverage.py can measure
• statement coverage
• branch coverage
• Coverage.py can produce reports in a number of formats
• text, HTML, XML, LCOV, and JSON.
• We will try to produce reports in HTML format.
17
Example 4 – Statement coverage
In this example, we will use coverage to measure the statement
coverage of the calculator test in Example 1.
1. Reuse calculator.py and test_calculator1.py in Example 1.
2. Run coverage run test_calculator_1.py in the terminal.
18
Example 4 – Statement coverage
3. A summary report .coverage will be generated.
4. Run coverage html in the terminal to generate the HTML report.
5. A folder htmlcov will be generated.
19
Example 4 – Statement coverage
6. Open htmlcov/index.html to view the coverage report.
20
You can achieve 100% coverage by adding test cases
for these two functions
Example 5 - Measurement with Django
• Reuse the orders/test.py we have created in Example 3.
1. Run coverage run manage.py test
2. Generate the HTML report
21
Example 5 - Measurement with Django
22
The report lists files along with
their coverage percentages, but
we are only interested in
model.py, the file being tested.
Example 5 - Measurement with Django
23
You can achieve 100% coverage by adding test case(s)
for the Manager model class, specifically for the string
representation function.
Example 6 - Branch coverage
• So far, we are measuring the statement coverage.
• To measure branch coverage, add the --branch flag.
• Since our current model does not include branch logic, add one to the model first
(orders/model.py).
24
Add a ‘weight’ field to Product
Add a ‘total_weight’ method to Order
that returns the sum of the weights of
the products in the order.
Example 6 - Branch coverage
• After editing the model, be sure to migrate the database
25
Example 6 - Branch coverage
• Add a test in test.py to test the total_weight() in the Order model.
• Note that total_weight() is tested when the order is empty, meaning the for
loop in total_weight() will not be executed.
26
Example 6 - Branch coverage
• After setting up the branch logic and test, run the coverage with
--branch flag
27
Example 6 - Branch coverage
• Now, view the coverage report
28
The yellow highlights indicate this branch is
partially run.
i.e., line 22 did not jump to line 23
You can achieve branch coverage by adding
test case(s) that involve this for loop, i.e.,
having an order with at least one product.
• A class that acts as a dummy web browser, allowing you to test your
views and interact with your DRF application programmatically.
• Simulate requests on a URL and observe the responses
• Supports methods such as .get(), .post(), .put(), .patch(), .delete(), .head() and .options()
• Allow you to check the URL and status code of the response.
• This test client does not require the web server to be running
APIClient
29
Let’s reuse the API endpoints from George’s lecture.
Router auto-generates viewnames. reverse() can be used instead:
• reverse('product-list') → "/api/products/"
• reverse('product-detail', args=[id]) → "/api/products/{id}/"
The response.data contains the serialized data for the response. It has been serialized from the data
model to Python primitives and is ready to be rendered.
Recall the API endpoints we have had
30
GET: Lists products
POST: Creates a product
GET: Retrieves a product
PUT: Updates a product
PATCH: Partial updates a product
DELECT: Destroys a product
• You can put the tests in another test*.py file.
Example 7 - Writing test cases with APIClient
31
If this assertion fails, all tests
associated with setUp() would
fail.
Be sure to use APITestCase
rather than TestCase
APITestCase initialises
APIClient to self.client by
default
Lists products
Creates a product
Example 7 - Continue to write more tests
32
Retrieves a product
Updates a product
Destroys a product
APIRequestFactory
• The APIRequestFactory shares the same API as the APIClient.
However, instead of behaving like a browser, this class provides a way
to generate a request instance that can be used as the first argument
to any view
• Standard methods are all available
• .get(), .post(), .put(), .patch(), .delete(), .head() and .options()
• Test a view function as a black box, with exactly known inputs and specific
outputs.
33
Recall the Product ViewSets
34
Provided actions:
• list
• create
• retrieve
• update
• partial_update
• destory
Example 8 - Tests with APIRequestFactory
35
list
36
retrieve
create
update
destroy
Summary
• We have learned how to test APIs with Django REST Framework
• Unit Test
• Test individual components in isolation
• Code coverage
• Measures how much of the code is covered by the tests
• APIClient
• Test the API on endpoints. Routes from the URL, build a request and call the view.
• APIRequestFactory
• Test the API directly on the view. Builds a request object that is passed to the view and
produces a response.
37