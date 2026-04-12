Our Use Case Definition:

(Group H)
Short Use Case Template for COMP3297: BetaTrax.
BetaTrax Use Case
UC ID and Name: BT-UC1 Handle product registration
Primary Actor: Product Owner Supporting Actors: User Authorization System
Trigger: A product participates in the beta testing program and is tracked in BetaTrax.
Description: The Product Owner registers a product in BetaTrax and associates the product
with its owner and developer so that defect reports can be received and
managed.
Preconditions: PRE-1: Product Owner is authenticated.
PRE-2: The product is not already registered in BetaTrax.
PRE-3: The Product Owner is not already assigned as the owner to another
product in BetaTrax.
PRE-4: Each selected Developer is authenticated to BetaTrax and is not already
assigned to another product.
Postconditions: POST-1: A new Product record exists with a unique Product ID.
POST-2: The Product Owner and Developers are linked to the Product.
Basic Flow: 1. Product Owner requests to register a new product and provides Product ID.
2. Product Owner provides the list of Developers to associate with the product.
3. System validates that Product ID is unique and that the owner and developers
are not assigned to another product.
4. System creates the Product record and stores owner and developer
associations.
Alternative Flows: 3a. Product ID already exists:
1. System rejects the request and indicates the Product ID is already
registered.
3b. Owner or Developer already assigned to another product:
1. System rejects the request and identifies the conflicting user(s).
2. Product Owner revises the request or cancels.
UC ID and Name: BT-UC2 Submit Defect Report
Primary Actor: Beta Tester Supporting Actors: Beta UI, Email Service
Trigger: Tester report a defect from the beta product UI after encountering an issue.
Description: A tester submits a defect report for a specific product and beta version.
BetaTrax assigns it an ID, sets the status to New, and stores it for Product
Owner evaluation.
Preconditions: PRE-1: Tester has a valid Tester ID.
PRE-2: The product is registered in BetaTrax.
PRE-3: The beta product can connect to the BetaTrax API.
Postconditions: POST-1: A new Defect Report is stored with status = “New” and a received
date/time.
POST-2: The report is associated with the specified Product ID and version.
Basic Flow: 1. Tester enters the defect report details: Product ID and version, title,
description, steps to reproduce, Tester ID, and optionally an email address for
notifications.2. Beta Product submits the report to BetaTrax.
3. System validates required fields and that the Product ID exists.
4. System assigns a unique Report ID, records the received date/time, and sets
status to “New”.
5. System stores the report and returns the Report ID to the Beta Product.
Alternative Flows: 3a. Unknown Product ID or invalid version:
1. System rejects the submission and returns an error.
2. Tester corrects the product/version and resubmits.
UC ID and Name: BT-UC3 Evaluate New Defect Report
Primary Actor: Product Owner Supporting Actors: Email Service, Backlog Tool
Trigger: A Product Owner reviews a newly submitted defect report with status = “New”.
Description: The Product Owner evaluates a New defect report and decides to accept, Reject,
or mark it as a Duplicate. If accepted, severity and priority are recorded and a
Product Backlog item reference is stored; the report status becomes Open.
Preconditions: PRE-1: Product Owner is authenticated.
PRE-2: The defect report exists and has status = “New”.
PRE-3: The defect report belongs to the Product Owner’s product.
Postconditions: POST-1: The defect report status is updated to one of: Open, Rejected,
Duplicate.
POST-2: If accepted, Severity and Priority are recorded and a Backlog item
reference is stored.
POST-3: If duplicate, the report is linked to the report it duplicates.
POST-4: If the tester provided an email address, a status-change notification
email is sent.
Basic Flow: 1. Product Owner requests the list of New defect reports for their product.
2. System displays the list; Product Owner selects a report.
3. Product Owner chooses “Accept” and records Severity, Priority, and the
Product Backlog item reference.
4. System records these values, sets report status to “Open”, and stores the
decision timestamp.
5. System sends a status-change email notification to the tester if an email
address was provided.
Alternative Flows: 3a. Reject report:
1. Product Owner chooses “Reject”.
2. System sets status to “Rejected” and stores the decision timestamp.
3. System emails the tester if an email address was provided.
3b. Mark report as duplicate:
1. Product Owner chooses “Duplicate” and selects the existing report it
duplicates.
2. System sets status to “Duplicate”.
3. System emails the tester if an email address was provided.
UC ID and Name: BT-UC4 Developer View and Take Defect
Primary Actor: Developer Supporting Actors: User Authorization System,
Email Service
Trigger: An Open defect is selected for work from the Backlog into the upcoming sprint,
and a developer chooses to take the ownership.
Description: A developer accepts responsibility for resolving an accepted defect report.
BetaTrax records the status change and notifies the tester by email if applicable.Preconditions: 1. PRE-1: The defect report exists and its status is Open.
2. PRE-2: The developer is authenticated and is part of the product’s
developer team.
Postconditions: 1. POST-1: The defect report is linked to the responsible developer.
2. POST-2: The defect status is updated to Assigned.
3. POST-3: The assignment timestamp/audit trail is recorded.
4. POST-4: The system sends an email notification to the tester to inform the
status change if applicable.
Basic Flow: 1. Developer views an Open defect report detail.
2. Developer takes responsibility for resolving the defect.
3. System records the developer assignment on the defect report.
4. System changes the defect status from Open to Assigned.
5. System confirms the assignment and shows the updated status/assignee.
6. System sends a notification email to the tester if an email address is
provided.
Alternative Flows: 3a. Developer declines/cancels taking ownership:
1. System does not record any assignments.
2. Use case ends (defect remains Open, no assignee recorded).
UC ID and Name: BT-UC5 Developer Update Defect as Fixed or Cannot Reproduce
Primary Actor: Developer Supporting Actors: User Authorization System,
Email Service
Trigger: The assigned developer finishes investigating the defect and either implements a
fix, or cannot reproduce the reported defect.
Description: The assigned developer updates the defect report after investigation. If a
correction is implemented, the developer marks the defect as Fixed. If the
developer cannot reproduce the issue, the developer marks it as Cannot
reproduce. BetaTrax records the status change and notifies the tester by email if
applicable.
Preconditions: 1. PRE-1: The defect report exists and its status is Assigned.
2. PRE-2: The developer is authenticated and is the developer assigned to the
defect.
Postconditions: 1. POST-1: The defect status is updated to Fixed or Cannot reproduce.
2. POST-2: The status change is recorded with date/time (audit/history).
3. POST-3: The system sends an email notification to the tester to inform the
status change if applicable.
Basic Flow: 1. Developer views an Assigned defect report detail.
2. Developer investigates and reproduces the defect.
3. Developer implements a correction.
4. Developer updates the defect status to Fixed.
5. System records the status change and timestamp and displays the updated
status.
6. System sends a notification email to the tester if an email address is
provided.
Alternative Flows: 3a. Cannot reproduce the defect:
1. Developer updates the defect status to Cannot Reproduce.
2. System records the status change and timestamp and displays the updated
status.
3. System sends a notification email to the tester if an email address is
provided.4. Use case ends.
UC ID and Name: BT-UC6 Project Owner Retest Defect and Finalize Outcome (Resolved or
Reopened)
Primary Actor: Project Owner Supporting Actors: User Authorization System,
Email Service
Trigger: A defect report is in Fixed status and is ready for retesting/verification
Description: The Product Owner retests a defect that a developer marked as Fixed. If the fix
is verified successfully, the Product Owner updates the status to Resolved. If
retesting fails, the Product Owner updates the status to Reopened and the defect
returns to the backlog for further work. BetaTrax records the status change and
notifies the tester by email if applicable.
Preconditions: 1. PRE-1: The defect report exists and its status is Fixed.
2. PRE-2: The Product Owner is authenticated and is the Product Owner of the
product.
Postconditions: 1. POST-1: The defect status is updated to Resolved or Reopened.
2. POST-2: The status change is recorded with date/time (audit/history).
3. POST-3: The system sends an email notification to the tester to inform the
status change if applicable.
Basic Flow: 1. Product Owner opens a Fixed defect report.
2. Product Owner retests the fix based on the defect’s reproduction steps (and
any updated notes).
3. Product Owner updates the defect status to Resolved if retest is successful.
4. System records the status change and timestamp and displays the updated
status.
5. System sends a notification email to the tester if an email address is
provided.
Alternative Flows: 3a. Retest fails (defect not corrected):
1. Product Owner updates the defect status to Reopened.
2. System records the status change and timestamp and displays the updated
status.
3. System sends a notification email to the tester if applicable.
4. Use case ends (defect is now available for rework via backlog workflow).
UC ID and Name: BT-UC7 Add Comment to Defect Report
Primary Actor: Product Owner &
Developer
Supporting Actors: User Authorization System
Trigger: The Developer or Product Owner needs to add detail or record a decision
regarding the defect.
Description: The Developer or Product Owner attaches a text comment to the defect report at
any point during its lifecycle to maintain a history of decisions.
Preconditions: 1. PRE-1: The defect report exists in the system.
2. PRE-2: The user is authenticated as the Product Owner or Developer.
Postconditions: 1. POST-1: The comment is saved and attached to the report.
2. POST-2: The comment text, current date, and author identity are
permanently recorded.
Basic Flow: 1. The Developer or Product Owner enters comment text on the defect report.
2. The system attaches the comment to the report.3. The system saves the comment with the text, the date it was attached, and
identifies the author.
Alternative Flows: 1a. Empty Comment Text
1. The Developer or Product Owner submits the comment, but the comment
text is empty or missing.
2. The system signals an error indicating that comment text is required.
3. The user either provides the text and resubmits, or cancels the operation.
1b. The user decides to cancel the comment
1. The user cancels the operation on the system.
2. The system discards any entered text and the use case ends

---

We are currently at Spring 1, here's Spring 1 Product Backlog:

SPRINT 1 — Required Slices  |  Lifecycle: New → Open → Assigned → Fixed → Resolved					
US-01	Submit a defect report with required fields	As a Beta Tester, I want to submit a defect report containing the product ID, version, title, description, reproduction steps, and my Tester ID so that the development team is informed of the issue I encountered.	"•submit defects with all required fields present in BetaProduct UI. 
• Report stored with status = 'New' in BetaTrax system.
• Missing required field returns 400 with descriptive error.
• Report ID and required field information returned in BetaTrax system 
"	Sprint 1	BT-UC2
US-02	Include optional email address in defect report	As a Beta Tester, I want to optionally provide my email address when submitting a defect report so that I can be notified of progress on its resolution.	"• Report submitted with email stores the address against the report.
• Report submitted without email is accepted and stored with no email.
• Email field is not required; omitting it does not cause an error."	Sprint 1	BT-UC2
US-03	Reject submission for unknown product	As a Beta Tester, I want to receive a clear error if I submit a report for an unrecognised product ID so that I know to correct the product details before resubmitting.	"• Submission with unknown product ID returns 404 / descriptive error.
• No report record is created for an invalid product.
• Valid product ID proceeds normally."	Sprint 1	BT-UC2
US-04	View list of New defect reports	As a Product Owner, I want to retrieve all defect reports with status 'New' for my product so that I can decide which ones to evaluate next.	"• Homepage displays a list of defects filterable by status.
• Selecting 'New' filters the list to show only New reports.
• Response includes Report ID, title, Product ID, Tester ID.
• Returns empty list (not error) when no New reports exist.
• Reports for other products are not returned."	Sprint 1	BT-UC3
US-05	Accept a defect report with Severity and Prioprity 	As a Product Owner, I want to accept a New defect report and record its Severity and Priority so that it can be added to the backlog for resolution.	"• After Entering the ""Severity / Priority"", and click on ""Accept(Open)"" button, the Status of defect change to ""Open"". 
• Severity must be one of: High,Medium, Low. 
• Priority must be one of: P1,P2,P3 (from higher pripority to low) 
• Only a New report can be accepted.
• Only the Product Owner of the product may accept."	Sprint 1	BT-UC3
US-06	Send email notification when defect is accepted	As a Beta Tester, I want to receive an email when my defect report is accepted so that I know it has been acknowledged and is being tracked.	"• When a report transitions to 'Open', an email is sent to the tester's address if one was provided.
• Email is not sent when no address is on the report.
• Email content identifies the report and new status."	Sprint 1	BT-UC3
US-07	View list of Open defect reports	As a Developer, I want to retrieve all Open defect reports for my product so that I can choose one to take responsibility for.	"• Homepage displays a list of defects filterable by status.
• Selecting 'Open' filters the list to show only Open defects.
• Response includes Defect ID, title,Product ID, severity, priority.
• Returns empty list when no Open reports exist.
• Defects for other products are not returned."	Sprint 1	BT-UC4
US-08	Take responsibility for an Open defect	As a Developer, I want to assign myself to an Open defect report so that the team knows I am responsible for resolving it.	"• Click on ""Take Ownership"" button and sets status to 'Assigned'.
• The ""Developer ID"" is auto entered by the system once logged in 
• Only an Open defect can be assigned.
• Only a developer on the product's team may assign themselves. "	Sprint 1	BT-UC4
US-09	Send email notification when defect is assigned	As a Beta Tester, I want to receive an email when a developer takes responsibility for my defect so that I know work has begun.	"• Email sent to tester address on transition to 'Assigned'.
• No email sent if no address is stored on the report.
• Email content identifies the report and new status."	Sprint 1	BT-UC4
US-10	Mark an Assigned defect as Fixed	As a Developer, I want to mark an Assigned defect as Fixed so that the Product Owner knows it is ready for retesting.	"• click on ""Set Fixed"" button changes status to 'Fixed'.
• Only the developer assigned to the report may mark it Fixed.
• Only 'Assigned' defects can be marked Fixed."	Sprint 1	BT-UC5
US-11	Send email notification when defect is marked Fixed	As a Beta Tester, I want to receive an email when the developer marks my defect as Fixed so that I know a fix has been applied.	"• Email sent to tester address on transition to 'Fixed'.
• No email sent if no address is stored.
• Email content identifies the report and new status."	Sprint 1	BT-UC5
US-12	View list of Fixed defect reports	As a Product Owner, I want to retrieve all Fixed defect reports for my product so that I can retest and close them.	"• Homepage displays a list of defects filterable by status.
• Selecting 'Fixed' filters the list to show only fixed defects.
• Response includes Defect ID, title, assigned developer."	Sprint 1	BT-UC6
US-13	Close a Fixed defect as Resolved	As a Product Owner, I want to mark a Fixed defect as Resolved so that the defect lifecycle is formally closed.	"• Click on ""Set Resolved"" button changes status to 'Resolved'.
• Only the Product Owner of the product may resolve.
• Retest Note may be enter if needed. 
• Only 'Fixed' defects can be resolved."	Sprint 1	BT-UC6
US-14	Send email notification when defect is Resolved	As a Beta Tester, I want to receive an email when my defect is marked Resolved so that I know the issue has been corrected.	"• Email sent to tester address on transition to 'Resolved'.
• No email sent if no address is stored.
• Email content identifies the report and new status. "	Sprint 1	BT-UC6

---

Current course instruction:

COMP3297 Software Engineering
School of Computing and Data Science
Department of Computer Science
Sprint 1 Task Sheet: BetaTrax
Sprint 1 Overview:
Your goal in Sprint 1 is to deliver an increment of BetaTrax that provides the most valuable functionality of a
Minimum Viable Product. This will require you to design and implement main success slices of several of your
use cases. In Sprint 2 you will implement the remaining functionality to take you to Release 1, a Minimum
Marketable Product.
By delivering these first slices of end-to-end functionality you will drive down the risk associated with your lack
of familiarity with Django and the Django Rest Framework, as well as further reducing the risk associated with
any misunderstanding of requirements.
You will also get a clearer idea of your development velocity and the amount of work your group can commit to
complete within a sprint timebox.
To better understand the needs of users, you will create throwaway UI prototypes in the form of wireframes for
review during the Sprint.
Tasks for Sprint 1:
UI Prototypes
Create UI storyboards for BetaTrax to present and discuss with your client during the sprint. You won’t
implement these. Their purpose is to confirm your understanding of requirements and of the data that must cross
the system boundary in API requests and responses. They should be Throwaway Prototypes showing rough UI
layout and flow for each of the use cases you wrote in Inception. Wireframe sketches on paper are sufficient.
You are not required to prototype the UI of products under test through which testers submit defects to
BetaTrax.
Create a Product Backlog
Your backlog is an ordered list of all work known to be required for the product, with highest priority PBIs at the
top. Create your Product Backlog as follows:
o Split your use cases into slices.
o For slices you will take into Sprint 1 (see below), write them as one or more
sprintable User Stories. Include a Confirmation section for each of those Stories.
o It’s common to use a spreadsheet-like format to record the product backlog, or to
use a 3rd party tool designed to manage backlogs. If you use a spreadsheet format,
your column headings at this point should be:
ID Title Description Confirmation
Note: the Title and the Description (“As a…I want…So that” ) together form the “Card” part of the story.Required Slices
Functionality for each of the following will appear in one or may be divided across several of your Inception
use cases. Actors are shown in square brackets. Take slices containing this functionality into Sprint 1:
o [Application under test] Submit a defect report in which the tester has supplied an email address.
o [Product Owner] View, evaluate and accept the defect, recording Severity and Priority.
o [Developer] View and take responsibility for a defect and fix it.
o [Product Owner] Close the defect as Resolved.
This represents a simple traversal of the defect lifecycle in which the defect status passes through the
following sequence, with email notifications sent accordingly:
New -> Open -> Assigned -> Fixed -> Resolved.
If you are confident in your team’s ability to deliver the listed functionality within the sprint, you may break
additional slices into stories, add them to the backlog and implement them in Sprint 1.
Remaining functionality
Place all remaining slices directly into the backlog as PBIs. You will break them into user stories ahead of
future sprints.
Analysis: Domain Model
Work from your User Stories for Sprint 1 to identify a set of conceptual classes and construct a partial Domain
Model in the form of a single class diagram for those stories. This will provide a basis for identifying resources
and for the design of your Django model classes.
Implementation
For the PBIs you are taking into Sprint 1, design your API, implement it on Django using the Django Rest
Framework and test the resulting increment. Your executable need only support a single registered product in
Sprint 1. In general, the actions crossing the system boundary from actor to BetaTrax recorded as steps in your
use case slices will indicate operations needed in your API.
Note: During Reading Week we will post an introduction to the Django Rest Framework.
Technical notes:
o User registration is not required in early MVP and MMP releases. You will register users through the
Django Admin Interface
o Similarly, product registration is not part of Sprint 1. You will perform product registration through
Django Admin.
o For convenience of testing and demos, it will be sufficient to configure Django to write all emails to the
console or to a file. Django provides backends for both. This is not a constraint, however, and you are
free to configure to use an actual mail server if you wish.
o Roughly track how long it takes to deliver each user story. This will be useful for planning future sprints.Tools: Git and GitHub
To support collaboration, you are required to use a version-control system (VCS) with remote repository or
repositories to coordinate your implementation work. You know Git from our prerequisite courses and will use
it for this project.
GitHub offers free public/private repositories with unlimited collaborators and all core features. That would be
a good choice as a hosting service. Choose the free plan here:
https://github.com/pricing
Delivering Source Code:
Deliver your source code by zipping the root directory of your Django project. Do not include a .git directory
or similar. Include a Readme file outlining any limitations of your Sprint 1 executable with respect to the
requirements – for example, list any planned functionality that is missing or not working correctly.
Demo and Review
Our first review session will take place during the week of March 30. It will also serve as an additional
checkpoint to ensure your team is not headed in the wrong direction. You will have the opportunity to select
your preferred timeslot when the date is announced. We don’t require every team member to be present. In the
session you will discuss and demonstrate your progress. You are not required to give a presentation.
SUMMARY OF SPRINT 1 DELIVERABLES
Note: there are separate deadlines
 Throwaway UI Storyboards for BetaTrax
 Product Backlog before taking PBIs into the Sprint. Indicate which PBIs you will take into Sprint 1
 Partial Domain Model
 Source code and Readme file
 List of team members’ contributions
Handin Method: Via Moodle, only one submission per team.
Deadlines: Storyboards: to be available by the end of March 19 ready for review with a
representative of your client on March 20.
Revised Storyboards, Product Backlog, Partial Domain Model: March 26. 23:59
Source Code, Readme file and List of members contributions: March 29, 23:59.
(At the original deadline, March 26, we will release instructions for populating your
application in preparation for the demo. We will give you a few days to ensure you can
do this successfully. Also, since there is a quiz during the sprint, we understand you
may need a little more time to work on the implementation. However, Sprint 2 will still
begin on March 26 to enable some team members to begin working on it while others
refine the Sprint 1 code.)

---

Sprint 2:
COMP3297 Software Engineering
School of Computing and Data Science
Department of Computer Science
Sprint 2 Task Sheet: BetaTrax
Sprint 2 Overview:
Thank you for your work during Sprint 1. We look forward to your demo in our Review Meeting next week.
Sprint 2 is straightforward since it simply follows the pattern of Sprint 1 to complete development of Release 1
of BetaTrax as a Minimum Marketable Product. By doing so you will clear the Release 1 Product Backlog.
Tasks for Sprint 2:
Backlog Refinement
Your backlog contains the remaining PBIs for Release 1, mostly as use case slices. If you have not included
user authentication yet, you must add this functionality to the backlog now. Then, as in Sprint 1:
o Split any unsliced use cases.
o Write all slices as one or more User Stories. Include a Confirmation section for each
of those Stories.
And, new for Sprint 2:
o Add a new column to your backlog labelled Estimate. For each PBI in the backlog,
estimate its relative size in Story Points and record your estimate in this column.
Note: You will continue to register users through Django Admin, however you are required to
support product registration by Product Owner in Release 1. You may continue to write all
emails to the console or to a file if you wish.
Sprint Planning
Decompose the stories and other PBIs you will bring into the Sprint into Tasks (Sub-Tasks if you are using
Jira). Record the member responsible for completing each Task. For future planning, keep a note of the efforthours taken for each Task during the sprint.
Analysis: Domain Model
Again, as before but now working from your user stories for Sprint 2, identify any new conceptual classes and
add them to your Domain Model together with their attributes and associations. You may also take the opportunity
to revise your previous model before adding the new classes.
Implementation
Design the remaining APIs for Sprint 2 and their realizations. Implement and integrate them into your previous
increment together with any changes needed to that increment. As in Sprint 1, deliver your source code by
zipping the root directory of your Django project. Do not include a .git directory or similar. Include a Readme
file outlining any limitations of your Sprint 2 executable with respect to the requirements.SUMMARY OF SPRINT 2 DELIVERABLES
 Product Backlog before taking PBIs into the Sprint.
 Sprint Backlog showing the tasks resulting from decomposing the PBIs, and their allocation to members.
 Revised and extended Partial Domain Model
 Source code and Readme file
 List of team members’ contributions
Handin Method: Via Moodle, only one submission per team.
Deadline: April 13, 23:59