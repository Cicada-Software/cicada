# Cicada Project Structure

There are a lot of moving parts to Cicada, and this is aimed to explain the core components
of Cicada, how they fit together, and where the code for each component is.

## The DSL

At the heart of Cicada is the Domain Specific Language (DSL) that is used in the `.ci` workflow files.
There are multiple steps required to run a workflow: parsing, AST generation, verification, and execution,
each of which is explained in detail below.

### The DSL: Parsing

> Defined in the `cicada/parse` folder.

The first step in parsing a `.ci` file is to turn it into a stream of tokens. For example:

```
1 + 2
```

is turned into the following stream of tokens:

```python
[
  IntegerLiteralToken('1'),
  WhiteSpaceToken(' '),
  PlusToken('+'),
  WhiteSpaceToken(' '),
  IntegerLiteralToken('2'),
]
```

Each token is a certain type, such as `IntegerLiteralToken`. Only the most basic checks are applied
at this level, such as checking all strings are closed.

### The DSL: AST Generation

> Defined in the `cicada/ast` folder.

Once we have a stream of tokens, we need to turn this into a tree-like structure that is easier to work with.
This type of tree is called an Abstract Syntax Tree, which is a tree representation of our program.

For example, the stream of tokens for `1 + 2` would have an AST tree similar to this:

```python
BinaryExpression(
  NumericExpression(1),
  BinaryOperator.ADD,
  NumericExpression(2),
)
```

If we cannot convert a certain token (or group of tokens) into an AST node, we have found a syntax error, and
we emit an error accordingly. If all is well and we successfully create an AST tree, we move on to the next stage.

### The DSL: Semantic Analysis

> Defined in `cicada/ast/semantic_analysis.py`.

Semantic analysis is where we "walk" the AST tree and verify that each node follows the semantics of the Cicada
language. This includes type checking, ensuring variables that are used actually exist, and more. Once we have
a valid AST tree we can use it to actually execute workflows.

### The DSL: Execution

> Defined in the `cicada/eval` folder.

Once we have parsed and validated an AST tree we can "walk" the tree like we did during semantic analysis,
except instead of validating the nodes we evaluate/execute them.

Workflows are executed in a variety of environments:

* Directly on the host machine: Usually done for testing purposes. Only should be done for trusted code.
* In a docker/podman container: The typical way of executing workflows. Can be used for insecure code.

More executors are planned to be added in the future to allow for users to run their workflows on different hardware,
different servers, or in different environments.

It is important to note that workflows run conditionally, that is, they only respond to certain triggers.
Before the workflow is executed, Cicada has to check that the workflow should actually be ran (that is,
the received trigger matches the trigger in the workflow), and that the received trigger matches the
`where` clause defied in the workflow (if it exists).

Take this workflow for example:

```
on git.push where event.branch is "main"

# do stuff
```

In this example, the workflow will only be ran if the received trigger is a `git.push` and the `branch` field
is `main`.

## The API

The API is responsible for connecting Cicada to the outside world. Some of it's responsibilities include:

* Handling webhooks from GitHub and Gitlab
* Querying/updating information stored in Cicada
* Serving static HTML/CSS/JavaScript files for the frontend
* Single-sign-on (SSO) via GitHub

The API is built in a Domain Driven Development (DDD) fashion. Domain Driven Development goes by many different names,
including Clean Architecture, Onion Architecture, Hexagonal Architecture, and many more. They all have a similar goal:
To build apps that are robust, configurable, and reduce coupling.

### The API: The Domain Layer

> Defined in the `cicada/api/domain` folder.

The domain layer is where the business objects are defined, such as Sessions, Workflows, Users, and more.
The main reason to have a domain layer is so that the business objects are well defined (in code),
and to invert the dependency on external services: The domain layer is at the center, and everything
else depends on the domain layer, not the other way around. This allows for decoupling of the business
logic from implementation details such as Git providers, APIs, and what database you store everything in.

The domain/business objects are different from database tables: Business objects are defined with the business logic
built into them, and are very strongly typed based on the business rules that apply to them. Database tables on the
other hand are less strongly typed, and often are stored in a different manner then they are compared to the business
objects. A single business object might be spread across multiple database tables, for example.

### The API: The Repository Layer

> Defined in the `cicada/api/repo` folder.

A repository is an interface that defines how data is accessed in Cicada. This interface specifies (using
the business terminology) how data should be accessed, but does not define how the data should be stored.
By using a repository layer you can easily swap implementations, so long as they conform to the same interface.
This makes testing easier, and allows you to more easily switch databases in the future.

Typical CRUD APIs use create, read, update, and delete as the verbs for accessing data; With repositories you
use the business terms for accessing data, such as `create_order`, `cancel_order` or `archive_order`. This means
you might have more or less than the 4 CRUD operations for a business object, depending on the business needs.

### The API: The Application Layer

> Defined in the `cicada/api/application` folder.

The application layer is where you define application services, which are business operations. Each application service
defines it's dependencies, usually one or more repository interfaces, and uses these interfaces to manipulate data
to achieve some business goal, such as creating a new user.

Application services define higher-level business goals, whereas domain objects define specific business rules for a
specific entity.

### The API: The Infrastructure Layer

> Defined in the `cicada/api/infra` folder.

The infrastructure layer is how we talk to external systems. There are 2 kinds of infrastructure in Cicada: Database
infrastructure, and API infrastructure.

For database infrastructure, a new class will be created that implements a certain repository interface. This new class will
translate high level business concepts (such as `cancel_order`) into the respective database calls. This allows application
services to speak using business terminology (via the interface) without having to worry about implementation details like
database table names and so forth.

For APIs, there usually isn't an interface to implement because the APIs are not interchangeable. For example, we wouldn't
create an interface for talking to GitHub's API since we depend on the specifics of GitHub's API. An interface might be
created later on for testing purposes, but for now it will remain as is.

### The API: The Presentation Layer

> Defined in the `cicada/api/endpoints` folder.

The presentation layer allows for the outside world to talk to Cicada, usually via HTTP API endpoints.

Each endpoint should do minimal business logic, as it is the responsibility of the application services to do the
heavy lifting. API endpoints should convert the incoming HTTP request (params, body, headers, etc)
into something that can be passed to an application service. Then, when the service is done, the output is converted
and sent back to the client.

There are examples where business logic is put in the endpoint directly, the primary example being websocket endpoints:
Due to the inherent technicalities of websockets, it's hard to decouple websockets in a way that works for an application
service, so it's better to leave the business logic in the websocket itself.

## The Frontend

> Defined in the `frontend` folder.

The frontend is the user-facing part of the app. It is currently written in plain HTML/CSS/JavaScript, though this
might change in the future. It is currently being served up via the API itself, though it will probably be switched
over to NGINX in the future.

Currently all the HTML files are defined in the `frontend/` folder, and all the static CSS/JavaScript is defined
in the `frontend/static` folder.

## Workflow Converter

> Defined in the `cicada/tools/workflow_converter` folder.

This is an experimental program to automatically convert workflows from other providers (such as GitHub Actions)
into Cicada workflows.
