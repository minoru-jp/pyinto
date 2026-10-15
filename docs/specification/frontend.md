# Python Frontend

This document specifies the implemented Python Frontend contracts for pyinto. The [Japanese canonical document](../../devdocs/canonical_documents/specification/frontend.md) remains authoritative. This English translation retains every clause, its acceptance and rejection conditions, normative level, and related-clause references. Normalization into the Model does not imply that a given Target can realize it.

## FRT_001

`PythonFrontend.parse(source)` parses input text using the Python AST and normalizes it into a `Program` and its child Construct structure. It does not execute the original Python program or mapped methods. It rejects unsupported syntax and unresolved references rather than filling gaps by conjecture.

title: Static normalization from the AST

level: MUST

related: [CST_001](construct.md#cst_001)

## FRT_002

As a rule, a new variable must be declared with a type annotation and an initial value. The only exception is introduction from a known element type at a `for` iteration entry under FRT_070. A plain reassignment to an existing name does not require redeclaring its type, but incompatible assignments are rejected. Ordinary types are currently limited to `int`, `str`, `bool`, `float`, `object`, explicitly imported `typing.Any`, and registered mapped classes. An ordinary type annotation is normalized into its notation and a single `ValueType`; an annotation of a mapped class is handled separately as a mapped-object declaration. No intermediate representation that splits a type into seven components is used.

title: Explicitly typed bindings

level: MUST

related: [CST_002](construct.md#cst_002)

## FRT_003

New typed bindings in the bodies of `if`, `while`, `for`, and `with`, and their `else` clauses, follow the restricted rules of FRT_071. Declaring or rebinding mapped objects in those blocks is rejected. New declarations in `try` clauses remain subject to FRT_021. Introducing a single `for` loop variable follows FRT_070; the binding target of `with ... as` must have been declared with a type before use. A `for` iterable is limited to an integer `range`, string, `list[T]`, or fixed-length `tuple`. It is accepted only if every known iteration-element type can be assigned to the target variable; an empty tuple needs no element-type check. General Iterables of unknown element type, dictionaries, and non-iterable values are rejected. `break` and `continue` require at least one enclosing loop.

title: Restrictions on name binding within control structures

level: MUST

related: [CST_003](construct.md#cst_003), [CST_005](construct.md#cst_005)

## FRT_004

`range()` accepts one to three positional arguments, each normalized as a Value of known integer type. Besides previously supported single comparisons and integer comparisons, comparison chains explicitly admitted by FRT_061 obey its restricted contract. The Frontend does not automatically supply arithmetic expressions beyond FRT_007–008 and FRT_060–061, implicit variable declarations, or unsupported statements.

title: Currently supported expression subset

level: MUST

related: [CST_004](construct.md#cst_004)

## FRT_005

Python-side Interface Mapping recognizes only functions and classes explicitly registered under fully qualified names in `InterfaceMappingRegistry`. The initial contiguous import section accepts `from module import function [as alias]`, `import module[.submodule] [as alias]`, and `from package import submodule [as alias]`. Only absolute imports are supported, and module-qualified function calls are resolved only against matching fully qualified Mapping registrations. Standard-library and third-party or custom libraries are treated alike. Importing a parent package alone does not make an unimported sibling submodule available. Unregistered modules, functions, or attributes, scope collisions, and dynamic references are rejected. Imported objects are neither loaded nor executed by Python.

An external function Mapping may register named parameters and their types through `InterfaceParameter`, together with trailing immutable Model-literal defaults, in addition to the legacy positional type sequence. For a named signature, Python positional and keyword arguments are bound to declaration order; excessive, unknown, duplicate, incorrectly typed, or missing required arguments are rejected. Omitted values are supplied from registered defaults without evaluating the argument expressions in source. Reordering keyword arguments when that would reorder side-effecting expressions is rejected, because arbitrary external Constructs have no universal representation of evaluation order.

`InterfaceVariadicParameter` supports a variadic positional parameter of homogeneous type whose argument count is statically known. The ordered arguments are passed to the factory without reevaluating Python expressions; dynamic argument unpacking is rejected. Multiple distinct signatures may be registered explicitly for one fully qualified function name. Names, counts, types, and defaults are matched and the factory invoked only when exactly one candidate is selected. Duplicate signatures are rejected at registration; zero or multiple matches are rejected while parsing, without using registration order as precedence. Argument expressions are normalized once, irrespective of the number of candidate signatures. Unpacked arguments, keyword-only arguments, and dynamic defaults are unsupported. Legacy positional-type-sequence Mappings retain their former admission rules.

`@maps(function)` decorates the parent class, and nested `@signature(...)` declarations with the class attribute `factory = ...` represent individual function signatures. `InterfaceMappingRegistry.from_declarations()` can explicitly convert them into the same `InterfaceFunctionMapping` type as before. `@maps` uses the referenced top-level function's defining `__module__` and `__qualname__` at declaration time for its fully qualified identity. There is no automatic registration; re-exported public names, arbitrary Callable or class/method Mapping parent/child declarations, and execution of Python functions while parsing source are unsupported. The special `_force` keyword for function Mappings is restricted to side-effect-free constants and removed during normalization.

title: Resolve only explicitly registered external API mappings

level: MUST

## FRT_006

Repeated use of one `PythonFrontend` instance must not carry variable declarations, function or module import aliases, loop depth, or mapped-object references from one `parse` request into the next.

title: Isolation of state between parse requests

level: MUST

## FRT_007

Binary `+`, `-`, `*`, `//`, and `%` and integer unary `+` and `-` in the Python AST are normalized as operations on explicitly integer-typed Values. Constant unary signs may still become a `Literal`. Integer-to-integer `/` and bitwise operations follow FRT_062. Operations such as `**` or operations without a declared type are rejected rather than inferred. Assigning to a new variable still requires a type declaration.

title: AST normalization of integer arithmetic

level: MUST

related: [CST_015](construct.md#cst_015)

## FRT_008

`and` and `or` become `BooleanOperation` while preserving Python AST operand order and nesting; `not` becomes `BooleanNot`. For now, operands are supported only when known to have Boolean type. The Frontend neither infers general Python truthiness nor pre-executes short-circuit evaluation.

title: AST normalization of Boolean expressions

level: MUST

related: [CST_016](construct.md#cst_016)

## FRT_009

Top-level `def` requires simple type annotations on all parameters and the return value. A separate scope is created for parameters and local variables, and `return` statements in the function normalize to `Return`. Return types are checked with the Model's assignability rules and diagnostics include source positions; Model construction independently validates explicit `Return` types. No inference is made that all execution paths return. A `return` outside a function is rejected.

title: Typed function definitions and local scopes

level: MUST

related: [CST_017](construct.md#cst_017), [CST_018](construct.md#cst_018)

## FRT_010

Signatures of top-level functions in the input module are collected before normalizing bodies, allowing structural resolution of forward references and recursion. Function calls are checked against their signatures for positional argument count and types. The Frontend rejects rather than guesses about decorators other than declarations with explicitly registered recognition/normalization handlers under FRT_058; defaults outside FRT_050–051; variadic parameters; keyword arguments outside FRT_048; nested definitions outside FRT_011; and unsupported types and bindings. Target Realizations for these new Models are not added at this stage.

title: Deterministic resolution and admission scope for functions

level: MUST

related: [CST_017](construct.md#cst_017), [CST_018](construct.md#cst_018)

## FRT_011

A typed `def` directly inside a typed function body is normalized into the existing recursive `FunctionDefinition`/`Block` structure. Signatures of definitions immediately inside each function body are collected in advance. Static lexical resolution searches from that function's immediately enclosing scope up to the module, resolving read-only references to outer typed values, direct calls by name, recursion, and forward references among sibling definitions. `Reference.symbol` and `FunctionCall.signature` preserve identity with the resolved declaration; identically named declarations in different scopes are distinguished by their ownership paths. No depth-specific Constructs are introduced.

title: Hierarchical lexical resolution of functions and recursive normalization

level: MUST

related: [CST_017](construct.md#cst_017), [CST_019](construct.md#cst_019)

## FRT_012

Allowing an inner function to read outer variables does not require returning the function as a value or implementing Python's dynamic closure machinery. The Frontend still rejects `nonlocal` that reassigns outer variables, `global` outside FRT_072, function-value operations beyond FRT_013, and function definitions inside control structures. Each scope reserves its local names without descending into nested function definitions, preventing use before declaration and erroneous resolution to an identically named outer declaration. A defined name in a parent scope does not automatically become writable from the inner scope. No new Realization is provided at this stage.

title: Explicit lexical-scope limits and unsupported behavior

level: MUST

related: [CST_019](construct.md#cst_019)

## FRT_013

For `typing.Callable` explicitly imported in the initial import section (possibly under an alias), `Callable[[...], ...]` with enumerated positional parameter types, including empty parameter lists and nested forms, is normalized in function, parameter, and typed-variable annotations. A reference to a function name used as a value produces a `Reference` to that signature's `value_symbol`. Initialization or reassignment of `Callable`-typed variables, passing function values as arguments to direct calls, `return` of function types, and direct `FunctionCall` returning a function type are accepted after static matching of the function types. References from nested functions that read outer variables reuse the existing scope representation: no special Closure Construct is defined.

title: Explicit Callable types and function-value references

level: MUST

related: [CST_020](construct.md#cst_020), [CST_021](construct.md#cst_021)

## FRT_014

Referring to and passing around a typed first-class function value is a different contract from calling that value. Indirect calls are specified separately by FRT_015–016, which lift the restrictions in force up to stage 10. Callable `...`, type inference, unregistered types, Callable shapes containing mapped types, rebinding through `nonlocal`, and dynamic manipulation of function attributes remain unsupported. Static reference/capture relationships are retained, but Realization is responsible for function lifetime, call environment, and whether the Target can implement them. Existing `with` and other semantic contracts are unchanged.

title: Function-value admission limits and a separate indirect-call contract

level: MUST

related: [CST_021](construct.md#cst_021)

## FRT_015

A call `f(args)` where a variable or parameter has an explicit `Callable` type, or an expression statically resolving to a function return value such as `factory(args)(args)`, is normalized into `FunctionValueCall`. The callee is retained as a child Value followed by ordered positional arguments. If the return type is itself a function type, another indirect call may follow. Traditional direct calls to a declared function name remain `FunctionCall` with their existing contract. Even for indirect calls, the Frontend neither executes source function bodies nor infers where runtime function values flow.

title: Normalization of indirect calls through function values

level: MUST

related: [CST_022](construct.md#cst_022), [CST_018](construct.md#cst_018)

## FRT_016

Calls through function values strictly validate positional argument count and each Value type against the callee's structural type. Keyword arguments, variadic arguments, non-function callees, and unknown type shapes are rejected rather than completed by inference. Reference and capture paths remain static Model information; the Frontend does not execute or predict dynamic function identity or the lifetime of captured environments. Because stage 11 adds no C/Python Target Realizations for these new Constructs, generation using an unsupported Realization fails explicitly. Existing contracts such as `with` remain unchanged.

title: Indirect-call limitations and the Realization boundary

level: MUST

related: [CST_022](construct.md#cst_022), [CST_021](construct.md#cst_021)

## FRT_017

The Frontend normalizes escaping function values from existing typed `def`, `Callable`, `Reference`, `FunctionCall`, and `FunctionValueCall` while preserving lexical declaration ownership paths and reference identities. Multiple function values obtained from one function declaration are not forced into one runtime environment; caller and argument expressions remain distinct structures. `nonlocal`, `global` beyond FRT_072, dynamic function attributes, outer locals used before declaration, and other unsupported dynamic operations remain rejected. Retaining this static information is not a substitute for verifying capture-environment lifetimes or shared references in the actual Target. Existing contracts, including `with`, are unchanged.

title: Preserve static closure paths without inferring runtime environments

level: MUST

related: [CST_023](construct.md#cst_023), [CST_024](construct.md#cst_024)

## FRT_018

The Python Frontend normalizes built-in explicit fixed-length `tuple[T1, T2, ...]` and empty `tuple[()]` annotations into `TupleType`. Expressions `(a, b)`, `(a,)`, and `()` become `TupleValue`, preserving element order and nesting. Tuple shapes propagate through declarations, reassignment, typed function parameters and returns, type arguments of `typing.Callable`, and passage of function values; mismatched types at corresponding positions or lengths are rejected. Source expressions or functions are not executed, and Target storage layouts are not inferred.

title: Normalization of fixed-length tuple expressions and explicit types

level: MUST

related: [CST_025](construct.md#cst_025)

## FRT_019

Tuple element reads accept only literal nonnegative integer indices, such as `t[0]`; the tuple shape and index bounds are checked before producing `TupleElement`. Nested accesses and calls of function-valued tuple elements such as `t[0](args)` are accepted, but general subscripting is not inferred. Variadic tuple types like `tuple[T, ...]`, negative or dynamic indices, slices, unpacking, element assignment, and full Python collection semantics are unsupported and explicitly rejected. No new tuple-related Target Realizations are registered at this stage; an unsupported Target Pack must reject realization. Existing `with` and other semantics are unchanged.

title: Static tuple access and restricted admission

level: MUST

related: [CST_025](construct.md#cst_025), [CST_026](construct.md#cst_026)

## FRT_020

The Frontend normalizes Python AST `try`/`except`/`else`/`finally` into an ordered structure of `Try`, `ExceptHandler`, and existing `Block` Constructs. Each `except` may name only `ValueError`, `TypeError`, or `RuntimeError`, or a tuple containing only those type names. `raise ValueError(...)`, `TypeError(...)`, or `RuntimeError(...)` becomes `Raise` only with no arguments or exactly one positional argument statically known to have string type. Such built-in names are not accepted if shadowed by source declarations, functions, imports, or similar bindings. The Frontend neither constructs exception objects nor evaluates message expressions.

title: Static normalization of a limited exception subset

level: MUST

related: [CST_027](construct.md#cst_027), [CST_028](construct.md#cst_028)

## FRT_021

The Frontend rejects unsupported exception features: `except ... as name` binding, bare `except:`, bare `raise` rethrowing, raising arbitrary classes, `raise ... from ...` cause chaining, `except*`/exception groups, multiple or keyword arguments, nonstring messages, and special exception-object operations. New typed bindings or mapped-object rebinding in `try` clauses are also rejected according to existing control-body rules. Control transfers containing `return`, `break`, or `continue` are retained structurally; Python exception execution is not inferred and remains a Realization responsibility. Target Realizations for the new exception Constructs are not registered. Existing `with`, function, expression, and scope semantics are not reinterpreted or changed.

title: Exception admission limits and unsupported Realizations

level: MUST

related: [CST_027](construct.md#cst_027), [CST_029](construct.md#cst_029)

## FRT_022

The Python Frontend normalizes explicit built-in `list[T]` types and `[value, ...]` with homogeneous element types into `ListType`/`ListValue`. Recursive element types propagate through declarations, reassignment, function parameters and returns, and nesting within `Callable` or `tuple`; empty `[]` is accepted only at declaration, assignment, return, or positional-argument sites with an unambiguous expected list type. `xs[index]` becomes `ListElement` retaining the integer index expression; `xs[index] = value` becomes `ListElementAssign` if the list name, integer index, and element type are known. Element updates to outer lists from nested functions are not name rebindings and use existing lexical references. Alias identity, negative indices, and runtime bounds checking remain part of Python source semantics; the Frontend does not execute operations or bounds checks.

title: Typed homogeneous lists and element updates

level: MUST

related: [CST_030](construct.md#cst_030), [CST_031](construct.md#cst_031)

## FRT_023

At this stage only a single explicit type argument in `list[T]`, list literals, reads by integer subscript, and element updates on variables are admitted. Empty `[]` without an expected type, mistyped elements, resizing via `append`/`extend`/`pop`, slices, comprehensions, unpacking, method calls, augmented assignments, and general untyped Python collection operations are rejected rather than inferred. Static tuple indexing and immutability remain unchanged. Target Realizations for the new list Constructs are not registered; a Target unable to guarantee list semantics and shared references must reject realization. Prior design decisions about `With`, exceptions, and other structures are not reinterpreted.

title: List admission limits and Realization responsibility

level: MUST

related: [CST_030](construct.md#cst_030), [CST_031](construct.md#cst_031)

## FRT_024

The Python Frontend normalizes explicit `dict[K, V]` annotations, where `K` is `int` or `str`, and `{key: value, ...}` into `DictType`, `DictEntry`, and `DictValue`. Without an expected type, a nonempty literal establishes its key/value shape from the first entry, and every entry is checked against that shape. Empty `{}` is accepted only where an explicit expected dictionary type is available, such as a declaration, assignment, return, or positional argument. Type shapes propagate recursively through functions, Callable, lists, tuples, and nested dictionaries. `d[key]` becomes `DictElement`; `d[key] = value` on a known dictionary variable becomes `DictElementAssign`. Existing lexical bindings distinguish element modification of an outer dictionary from rebinding its name. Python expressions are not executed statically.

title: Normalization of typed dictionaries: literals, subscripting, and updates

level: MUST

related: [CST_032](construct.md#cst_032), [CST_033](construct.md#cst_033)

## FRT_025

At this stage dictionaries are limited to `int` or `str` keys, one explicit value type, literals, typed-name bindings, element reads by subscript, and element insertion/update on a simple dictionary variable. Mixed or compound key types, empty dictionaries without expected static types, `{**mapping}`, dictionary comprehensions, `dict(...)` construction, `get`/`update`/`pop` and other methods, `del`, dictionary iteration, generic key-identity inference, and Python reflection are not accepted. The `KeyError` semantics of a missing key on subscript read do not introduce a new catchable type in the current restricted exception Constructs. Dictionary Target Realizations are not registered; a Target unable to implement ordering, value updates, alias sharing, and lookup-failure semantics must explicitly reject realization. Existing `with`, tuple, list, and exception contracts are unchanged.

title: Restricted dictionary admission and Realization boundary

level: MUST

related: [CST_032](construct.md#cst_032), [CST_033](construct.md#cst_033)

## FRT_026

The Frontend normalizes module-level `class` declarations without class decorators or metaclasses as nominal declarations; static single inheritance is separately specified in FRT_029–031. Every class requires an explicit `__init__` returning `None` and ordinary typed instance methods. The unannotated first parameter of a method is normalized to the owning class type with `ParameterRole.RECEIVER`, even if its name is not `self`. Fields are extracted statically from a contiguous series of `receiver.name: T = value` declarations at the beginning of `__init__` (immediately after the required `super().__init__` in a derived class), and only initialized fields may be accessed. Attribute reads and writes, creation with explicit positional arguments, and method calls are modeled with links to types and declaration owners. Source code is not executed, and arbitrary class construction or special-method behavior is not inferred.

title: Normalization of static classes, typed instances, and receivers

level: MUST

related: [CST_034](construct.md#cst_034), [CST_035](construct.md#cst_035), [CST_036](construct.md#cst_036)

## FRT_027

For now, only nominal instance types, directly declared fields and ordinary instance methods, and restricted construction, reference, and update operations are accepted. Rejected features include inheritance mechanisms beyond static single inheritance and bare `super()` admitted by FRT_029–031; custom `__new__`; special methods other than `__init__`; class attributes; inherited method lookup outside the supported inheritance rules; `staticmethod`, `classmethod`, `property`, descriptors, `__getattribute__`/`__setattr__`, dynamic attribute additions, decorators, operations treating class objects as values, rebinding receivers, method argument forms outside FRT_048, and conditional field declarations. Class bodies contain only directly declared methods, and method names reside in a dedicated class namespace. Unqualified method names in method bodies are not implicitly resolved as function references. Ordinary module-function references retain their lexical resolution behavior.

title: Restricted admission of Python's dynamic class machinery

level: MUST

related: [CST_034](construct.md#cst_034), [CST_035](construct.md#cst_035)

## FRT_028

No Target Realizations are added for `ClassDefinition`, `InstanceCreation`, `FieldRead`, `FieldWrite`, `FieldInitialize`, or `MethodCall`. Conversion to a Target Pack that does not support them fails explicitly during Realization, without mutating the original Model. Guaranteed contracts include nominal class types, receiver roles, attribute declaration ownership, and shared value references. Admitting classes does not justify modifying existing semantic contracts for `with`, functions, exceptions, tuples, lists, or dictionaries.

title: Unsupported class Realizations and preservation of existing specifications

level: MUST

related: [CST_034](construct.md#cst_034), [CST_036](construct.md#cst_036)

## FRT_029

`class Derived(Base)` is admitted only if `Base` is the simple name of a static single base class already defined in the same module. The base must be an AST Name, not a class expression or dynamic operation; undefined bases, self-inheritance, multiple inheritance, metaclasses, and class decorators are rejected. The Frontend uniquely links `InstanceType.base` and `ClassSignature.base`, resolving inherited fields and methods through recursive declaration references. Requiring the base to be declared first is a Frontend admission rule at this stage and does not constrain a Realization's memory layout.

title: Frontend admission boundary for static single inheritance

level: MUST

related: [CST_037](construct.md#cst_037)

## FRT_030

A derived `__init__` requires exactly one leading `super().__init__(args)` using a zero-argument `super()`. Two-argument `super` and dynamic base operations are not supported. The initializer call statically invokes a base method on the same Receiver; it does not construct another base instance. Newly typed fields must be declared immediately after that leading call, and inherited fields can be read after base initialization. Ordinary `super().method(args)` is admitted in ordinary methods inside classes, resolving the signature statically by searching the immediate base of the method's lexical owning class. Using `super().__init__` outside a method or constructor is rejected.

title: Static resolution of base initialization and super

level: MUST

related: [CST_038](construct.md#cst_038)

## FRT_031

An instance may be assigned, passed, or returned through a typed base-class reference; the Frontend does not guess and freeze its actual runtime class from the AST. Ordinary `obj.method(args)` is normalized as a `MethodDispatch.VIRTUAL` call after checking an accessible method signature against the static receiver type. Realization must select the correct implementation using the runtime class and static inheritance hierarchy. Derived overrides other than `__init__` must match the type shape. Unrelated nominal types, implicit downcasts, mismatched overrides, `super` outside the static class context, and unsupported Target implementations are explicitly rejected. Existing `with` and other semantics are unchanged.

title: Virtual calls in the static class hierarchy and their boundaries

level: MUST

related: [CST_037](construct.md#cst_037), [CST_038](construct.md#cst_038), [CST_039](construct.md#cst_039)

## FRT_032

In addition to simple names and constructors, a statically typed instance value may be a method receiver when obtained from an element read of a typed list, dictionary, or fixed-length tuple, from a function or method return, or from chained instance fields. The Frontend does not execute these expressions as Python; it retains the value expression beneath `MethodCall.receiver`. Declared methods are checked against the static receiver type, and ordinary calls always use `MethodDispatch.VIRTUAL`. Determining the actual instance class and selecting the implementation remains the Realization's responsibility, not a static guess.

title: Virtual method calls on typed instances from compound expressions

level: MUST

related: [CST_040](construct.md#cst_040), [CST_038](construct.md#cst_038)

## FRT_033

For an instance call `obj.member(args)`, a statically resolved ordinary method becomes the existing virtual `MethodCall`. If `member` is a field with explicit `Callable` type, the call becomes a `FunctionValueCall` whose callee is `FieldRead`. Ownership of inherited function-valued fields is retained; the latter call does not add an implicit Receiver. Chained instance fields are represented with existing `FieldRead` nodes. Constraints on indirect-call positional arguments, their number and types, remain unchanged. Calls through `super()` retain `MethodDispatch.SUPER`.

title: Distinguishing method calls from function-valued field calls

level: MUST

related: [CST_041](construct.md#cst_041), [CST_022](construct.md#cst_022), [CST_038](construct.md#cst_038)

## FRT_034

Receivers with unknown types, undefined members, calls to non-Callable fields, wrong argument counts/types, unsupported keywords or unpacked arguments, and implicit nominal downcasts remain rejected. Existing tuple/list/dictionary shape rules and the restriction that element assignments target simple declared list/dictionary variables remain unchanged. Accepting compound receivers does not add Target Realizations: generation fails explicitly if class, inheritance, function-value, or collection realization is missing. Existing `with` and other semantics are unchanged.

title: Boundary checking for classes and compound values; unsupported Realizations

level: MUST

related: [CST_040](construct.md#cst_040), [CST_041](construct.md#cst_041)

## FRT_035

Exact Python AST Boolean constants `True` and `False` normalize to `BooleanLiteral`, not an integer `Literal`. They may be used in Boolean declarations and reassignments, `if`/`while`, and as Boolean operands of existing `BooleanOperation`/`BooleanNot`. Neither general Python truthiness nor implicit bool/int type compatibility is adopted; a Boolean constant in an integer-typed position is rejected as a type mismatch.

title: Typed normalization of Boolean constants

level: MUST

related: [CST_042](construct.md#cst_042)

## FRT_036

A Python AST `None` expression generally normalizes to a `NoneLiteral` Value. It is allowed in explicitly `object`- or `typing.Any`-typed variables, function arguments, and returns. This does not introduce a declared `None` type, implicit `Optional`/`Union`, or broaden element-type rules for existing `list[T]`, `dict[K,V]`, and fixed-length tuples. In existing functions returning `-> None`, both `return` and `return None` remain the same `Return()` as before. `None` is not silently converted to other types; mismatches are rejected explicitly.

title: Limited treatment of None as a general expression Value

level: MUST

related: [CST_043](construct.md#cst_043)

## FRT_037

`a if condition else b` (`ast.IfExp`) normalizes to `ConditionalExpression` with `condition` required to be strictly `ValueKind.BOOLEAN`. If a declaration, assignment, function argument, return, or similar position supplies an explicit expected `ValueType`, both branches are checked for assignability to it. Otherwise the branches' `value_type` values must be exactly equal. No inferred common type or implicit Union is constructed. Condition and branch ASTs are not executed; evaluation order and non-evaluation of the unselected branch are preserved in the Model.

title: Static type checking and AST normalization of conditional expressions

level: MUST

related: [CST_044](construct.md#cst_044)

## FRT_038

Adding Boolean constants, None Values, and conditional expressions does not reinterpret existing semantics of `Literal`, `Return`, `With`, exceptions, typed collections, or classes. General Python truthiness, dynamic Union/Optional and inference, treating Boolean as integer, and Target Realizations for these three added structures remain unsupported. The Frontend rejects explicit type mismatches; Realization rejects unsupported Target implementations.

title: Admission boundary and missing Realizations for three new features

level: MUST

related: [CST_042](construct.md#cst_042), [CST_043](construct.md#cst_043), [CST_044](construct.md#cst_044)

## FRT_039

An unshadowed `len(expression)` becomes `Length`, accepting exactly one positional argument with statically known `str`, `tuple`, `list`, or `dict` type. The argument expression is retained from the Python AST; string and tuple lengths are not pre-evaluated. Untyped `object`/`Any`, user-defined classes, keywords, `*args`, and incorrect argument counts are rejected explicitly. No general Python `__len__` lookup mechanism is introduced.

title: Restricted normalization of built-in len syntax

level: MUST

related: [CST_045](construct.md#cst_045)

## FRT_040

An unbound direct `abs(x)` becomes integer `Absolute`; `min(a, b, ...)` and `max(a, b, ...)` become integer `Extremum`. `abs` requires one positional argument; `min` and `max` require at least two; all operands must be strictly `ValueKind.INTEGER`. Operand expressions and argument order are retained and not evaluated by the Frontend. Existing resolution of same-named user-defined functions, function-typed variables, and registered mappings takes precedence.

title: Typed integer normalization of abs, min, and max

level: MUST

related: [CST_046](construct.md#cst_046), [CST_047](construct.md#cst_047)

## FRT_041

The new primitive operations do not imply general support for Python built-ins. Unsupported cases include `zip`/`enumerate`, floating-point or general-object `abs`, one-Iterable-argument `min`/`max`, `key=`/`default=`, dynamic attribute references, and extensions through special methods. No `Length`, `Absolute`, or `Extremum` Realizations are provided; producing a Model does not make generation succeed without corresponding Target Realizations. Existing semantics of `Range`, `Call`, `With`, arithmetic, and collections are not changed.

title: Built-in operation admission boundaries and missing Realizations

level: MUST

related: [CST_045](construct.md#cst_045), [CST_046](construct.md#cst_046), [CST_047](construct.md#cst_047)

## FRT_042

Unbound direct calls `sum(iterable)` and `sum(iterable, start)` normalize to `IntegerSum`. The iterable must be `list[int]`, a fixed-length tuple whose elements are all `int`, or an existing integer `range(...)`; `start` must be an integer Value. An omitted start does not synthesize an extra call-side effect. Only one or two positional arguments are supported. Iterable and start expressions and their evaluation order are preserved, not aggregated by the Frontend. Untyped empty lists, strings, dictionaries, Booleans, and other unsupported forms of `sum` are explicitly rejected.

title: Restricted AST normalization of integer sum

level: MUST

related: [CST_048](construct.md#cst_048)

## FRT_043

Unbound direct `any(iterable)`/`all(iterable)` calls become `BooleanAggregate`. Exactly one positional argument is permitted, consisting of `list[bool]` or a fixed-length tuple (including the empty tuple) whose elements have strict Boolean type. No general truthiness is inferred; short-circuit evaluation remains a Model contract. Argument expressions are neither executed nor constant-folded.

title: Boolean-only normalization of any and all

level: MUST

related: [CST_049](construct.md#cst_049)

## FRT_044

If `sum`, `any`, or `all` resolves to an existing function declaration, a typed function variable, or a registered mapping, that resolution takes precedence and the call is not intercepted as a built-in operation. Keyword/unpacked arguments, undeclared general Iterables, unsupported element types, and invalid argument counts are rejected explicitly. `IntegerSum` and `BooleanAggregate` Target Realizations are not yet provided; successful Model normalization does not guarantee execution on the Target. Existing semantics for `Range`, `Call`, `With`, `Length`, `Absolute`, and `Extremum` are unchanged.

title: Name resolution and Target boundaries for aggregate built-ins

level: MUST

related: [CST_048](construct.md#cst_048), [CST_049](construct.md#cst_049)

## FRT_045

Python AST `float` annotations and finite float literals normalize into `ValueKind.FLOAT`/`FloatingLiteral`. Arithmetic `+`, `-`, `*`, `/`, unary signs, and same-type float comparisons become dedicated Constructs; existing static type checks apply within functions, Callable types, and collections. Implicit int/float conversions, float `//` or `%`, complex values, and calls to the `float()` constructor are not admitted.

title: Normalization of floating-point types and expressions

level: MUST

related: [CST_050](construct.md#cst_050), [CST_051](construct.md#cst_051), [CST_052](construct.md#cst_052)

## FRT_046

`str + str` becomes `StringConcat`; `str * int` or `int * str` becomes `StringRepeat`; the six comparisons between strings become `StringComparison`; `str in str` and `str not in str` become `StringContains`; and `str[int_expr]` becomes `StringElement`. String Values, index expressions, and comparison expressions are preserved from the AST rather than calculated by the Frontend. Comparison chains, slices, and attribute handling on arbitrary dynamic objects are outside this contract.

title: Basic string operations and static type checking

level: MUST

related: [CST_053](construct.md#cst_053), [CST_054](construct.md#cst_054), [CST_055](construct.md#cst_055)

## FRT_047

The new float and string Constructs do not change semantic contracts of existing `Literal`, integer `Arithmetic`, integer-only `Absolute`/`Extremum`/`IntegerSum`, `Length`, `With`, or other established nodes. Realizations for the new structures are not yet supplied: Targets unable to implement Python float operations or string Unicode/`IndexError` semantics must reject explicitly. General Python object protocols and precision-specification Interfaces are not inferred or introduced.

title: String and floating-point admission restrictions and Target boundary

level: MUST

related: [CST_050](construct.md#cst_050), [CST_053](construct.md#cst_053), [CST_055](construct.md#cst_055)

## FRT_048

Ordinary positional and named keyword arguments may be mixed only for statically resolved `FunctionCall`, class-construction `InstanceCreation`, and receiver-based `MethodCall` (ordinary or `super()`). Arguments are statically bound by parameter name and `arguments` is arranged in declaration order, while `evaluation_order` separately retains the Python AST evaluation order of positional argument expressions followed by keyword expressions. The receiver expression is evaluated once before call arguments. Existing contracts for types, declaration scopes, and virtual/`super()` dispatch remain unchanged.

title: Separate normalization of static keyword binding and source evaluation order

level: MUST

related: [CST_056](construct.md#cst_056)

## FRT_049

Unknown keyword names, duplicate bindings, missing required arguments, type mismatches, excessive positional arguments, and `*args`/`**kwargs` unpacking are rejected without inference. Because `CallableType` has no parameter names, keyword arguments to `FunctionValueCall` remain unsupported. Built-ins, special mapped-function calls, arbitrary default expressions not admitted by FRT_050–051, positional-only or keyword-only parameters, and dynamic function transformations are outside this change. Generation rejects absent Target Realizations. New contracts do not reinterpret existing `With`, numeric, class, or closure semantics.

title: Keyword argument restrictions, static checks, and realization responsibility

level: MUST

related: [CST_056](construct.md#cst_056)

## FRT_050

The Frontend admits trailing default arguments on typed `def` functions and instance methods taking positional arguments, including `__init__` and calls via `super()`, only when the defaults are literals of integer, finite float, string, Boolean, or None. Integer/float literals with unary `+` or `-` are permitted; arithmetic expressions, name references, function calls, compound defaults (lists, dictionaries, tuples, etc.), `*args`/`**kwargs`, and positional-only or keyword-only arguments are rejected. Defaults inconsistent with annotated types are rejected; `None` defaults are admitted only for `object` or explicitly imported `Any` types. Values are normalized statically while collecting function declarations, without executing input code.

title: Admission and rejection of restricted static default arguments

level: MUST

related: [CST_057](construct.md#cst_057)

## FRT_051

For statically resolved direct function calls, instance creation, and ordinary or `super()` method calls, the Frontend supplies omitted arguments using immutable literal defaults declared in the signature. Every `arguments` Slot retains a value in formal-parameter order. `omitted_arguments` identifies omitted positions, while `evaluation_order` records the positions of omitted literals after the evaluation order of explicitly supplied arguments. Realization must evaluate the callee/Receiver once, evaluate only source-written argument expressions once each in source order, and fill missing parameters with the static defaults. This does not implement general Python definition-time expression evaluation, sharing of mutable defaults, omission in indirect calls inferred from `CallableType` arity, or implicit decorator rewriting. Changing a default in an override is rejected to avoid inconsistent behavior when calling through a base-typed reference. Existing `With` and other Construct semantics are unchanged.

title: Per-call completion of omitted arguments and evaluation order of explicit arguments

level: MUST

related: [CST_056](construct.md#cst_056), [CST_057](construct.md#cst_057)

## FRT_052

Only the unshadowed built-in `@staticmethod` decorating an ordinary typed `def` in a class body is admitted as `MethodKind.STATIC`. Every parameter has an explicit type, without a Receiver; calls must use `ClassName.method(...)`, with class name and method declaration resolved statically. Formal parameter types, named arguments, restricted defaults, and evaluation order are retained. Accessing a staticmethod through an instance or extracting a staticmethod as a value is outside the initial contract.

title: Selective static normalization of staticmethod

level: MUST

related: [CST_058](construct.md#cst_058)

## FRT_053

The Frontend assigns the `CLASS_RECEIVER` role to the first formal parameter of a typed `@classmethod`, regardless of its spelling. `ClassName.method(...)` and `receiver.method(...)` within the method are normalized as class-method calls; `receiver(args...)` is normalized as `ClassReceiverCreation`. When a classmethod declared on a base class is called from a subclass under static single inheritance, the runtime class remains the derived class. The method body does not create a fixed base-class instance. Arbitrary class-object references, reflection, metaclasses, and instance-based classmethod calls are not accepted.

title: Runtime identity of the class receiver and restricted operations

level: MUST

related: [CST_059](construct.md#cst_059)

## FRT_054

The Frontend accepts `@dataclass` only when `from dataclasses import dataclass` (optionally aliased) was explicitly imported at the beginning, the decorated class has no base class, and the decorator name has not been shadowed. Class-body typed fields `name: T` and `name: T = scalar_default` are collected in declaration order; a static initializer and existing `FieldInitialize` nodes are constructed. Required fields following defaulted fields, a custom `__init__`, arbitrary default expressions, `field()`, and dataclass options are rejected. The synthesized initializer obeys existing instance-creation, default-value, and keyword-argument semantic contracts.

title: Restricted dataclass fields and synthesized initialization

level: MUST

related: [CST_060](construct.md#cst_060), [CST_057](construct.md#cst_057)

## FRT_055

The Frontend does not infer general Decorator AST behavior, evaluation/application of decorator functions, replacement by decorator return values, or complete Python descriptor, metaclass, or dataclass semantics. Existing contracts for ordinary instance methods, inheritance, `with`, and other features remain intact. Static methods, class methods, and restricted dataclasses have separate Model contracts; missing Target Realizations fail explicitly.

title: Limits of selected decorators and realization responsibilities

level: MUST

related: [CST_058](construct.md#cst_058), [CST_059](construct.md#cst_059), [CST_060](construct.md#cst_060)

## FRT_056

The Python Frontend normalizes `ast.Lambda` to `LambdaValue` only when the context, such as a declaration, return, argument, typed collection element, or typed conditional expression, determines an explicit expected `Callable[[...], R]` type. Each unannotated lambda parameter is assigned its corresponding `CallableType.parameter_types` entry, and the single expression body must match `CallableType.return_type`. Every lambda receives a nonconflicting generated name and an independent lexical scope while preserving references to outer `Symbol` and function declarations. Nested lambdas, returned function values, typed function arguments, and list/tuple elements reuse existing structures. Source code is not executed, and arbitrary return-type inference is not performed.

title: Typed lambda normalization in an explicit Callable context

level: MUST

related: [CST_061](construct.md#cst_061), [CST_020](construct.md#cst_020), [CST_023](construct.md#cst_023)

## FRT_057

Lambda expressions without a determinable expected type, wrong parameter count, defaults, positional-only or keyword-only parameters, variadics, argument unpacking, body type mismatches, and unresolved names are rejected explicitly. A lambda returning `None` is admitted only when its body is the `None` expression. General Python function-object attributes and dynamic decorator behavior are not accepted. Target Realizations for lambda definitions, captures, or function values are not provided at this stage, so conversion rejects absent registrations. Existing contracts for `with`, classes, defaults, and other structures are unchanged.

title: Lambda admission boundary and Realization boundary

level: MUST

related: [CST_061](construct.md#cst_061)

## FRT_058

Decorators are identified by a fully qualified name, application target (`class`, `method`, or `function`), and explicit effect name registered in `DecoratorRegistry`. Aliases from explicit imports are bound independently per parse request; built-in `staticmethod`/`classmethod` and imported `dataclass` are resolved as registered rules. Registration of a recognition rule is separate from registration of a normalization handler for its target and effect; absence of the latter always causes rejection. A method handler determines `MethodKind`. A class handler declares, through `ClassDecorationPlan`, additions such as methods normalized into existing Constructs. A function handler may transform an already constructed `FunctionDefinition` into another `FunctionDefinition` with the same signature. A class normalization plan is derived only once for the same declaration within a parse request. The three built-in decorators use the same handler mechanism, retaining FRT_052–055 contracts and rejection conditions. Dynamic decorator invocation or evaluation, general composition order for multiple decorators, and guessing Python semantics without a registered handler are not supported. The explicitly registered handler defines the constructed Model's semantics; Target feasibility is left to Realization. General replacement by Constructs or Interfaces beyond currently supported handler return types remains unimplemented.

title: Boundaries of registered decorator recognition and effect normalization

level: MUST

related: [CST_058](construct.md#cst_058), [CST_059](construct.md#cst_059), [CST_060](construct.md#cst_060)

## FRT_059

The Python Frontend normalizes `ast.Pass` to a `Pass` at its source position. In a module, typed function or method, or static class declaration, only a first statement that is a constant string expression is recognized as a docstring; its value is retained in the corresponding Model declaration's `docstring` and removed from executable statements. A leading docstring in a class or restricted `@dataclass` does not count as a typed field or method; a leading docstring in `__init__` does not change existing initialization-order checks. Standalone string expressions that are not first, f-strings, and general string-expression evaluation are not newly accepted. Docstring presence does not imply Target generation of `__doc__` attributes or Python introspection. Conversions needing an unregistered `Pass` Realization retain the usual missing-registration rejection.

title: Restricted normalization of pass and declaration docstrings

level: MUST

related: [CST_062](construct.md#cst_062)

## FRT_060

The Python Frontend normalizes `ast.AugAssign` into `AugAssign` only when its target is a previously declared ordinary name or an instance field with a statically resolved type, and an operation between `int` scalars or between `float` scalars of the same type is valid. A field Receiver expression is normalized once; the original assignment target is not copied into the right-hand expression. For integers, `+=`, `-=`, `*=`, `//=`, `%=` and bitwise augmented assignments from FRT_062 are admitted; for floats, `+=`, `-=`, `*=`, `/=`. Name targets of `ast.AugAssign` participate in advance reservation of Python function-local names, preventing accidental resolution of same-named module or outer-function values for augmented assignments inside functions without explicit `global`. Explicit global names permitted under FRT_072 are allowed in existing `AugAssign` while retaining their original module Symbols. Undeclared names, rebinding an instance Receiver, fields used before initialization, list/dict `+=`, augmented assignment to subscripts, exponentiation, and other unsupported forms are rejected explicitly. Ordinary assignment, field updates, exception paths, and existing type contracts are unchanged.

title: Static normalization of restricted scalar AugAssign

level: MUST

related: [CST_063](construct.md#cst_063)

## FRT_061

A Python AST `ast.Compare` with two or more consecutive comparison operators becomes `ComparisonChain` only when all operand types are exactly the same (`int`, `float`, or `str`) and all operators are one of the six ordering/equality comparisons. Each constructed operand Value is retained exactly once in source order; the Frontend does not duplicate it into binary comparisons and Boolean expressions. Existing normalization of a single `Comparison`, `FloatingComparison`, or `StringComparison` is preserved. Chains with mixed types, `in`, `not in`, `is`, or `is not`, and arbitrary comparison protocols are rejected without inference.

title: Static scalar comparison chains versus existing binary comparisons

level: MUST

related: [CST_064](construct.md#cst_064)

## FRT_062

The Python Frontend normalizes `/` between two explicitly integer-typed Values into `IntegerTrueDivision`, with result type `float`. It does not permit implicit narrowing to an `int` variable, mixed-type division, or pre-evaluation of expression values. Binary integer `&`, `|`, `^`, `<<`, and `>>`, and unary integer `~`, normalize to typed existing `Arithmetic`/`IntegerUnary` nodes. Expressions are not executed or inferred for negative shifts or huge integers; their runtime semantic contracts remain in force. `&=`, `|=`, `^=`, `<<=`, and `>>=` targeting a previously declared integer name or typed field become `AugAssign` under existing scalar rebinding contracts. Float bitwise operations, implicit bool-to-int, mixed int/float operations, exponentiation `**` or `**=`, and integer `/=` remain rejected. No new Realizations are required of the standard Python/C Target Packs.

title: Integer true division and typed bitwise-operation normalization

level: MUST

related: [CST_065](construct.md#cst_065)

## FRT_063

`PythonFrontend(intrinsics=IntrinsicRegistry(...))` normalizes only explicitly registered primitive operations, using their resolved static type signatures, into `IntrinsicCall`. When `intrinsics` is omitted, the default provider table from FRT_065 is used. Existing special Constructs for `len`, `abs`, `min`, etc. remain in place; arbitrary Python built-ins or attributes are not automatically admitted. For a direct-name call, same-named declared functions, typed Symbols, mapped names, classes, and similar bindings take precedence; only explicitly registered names without such conflicts are treated as intrinsics. For an attribute call, existing static instance methods, `super`, and class methods resolve first. Only remaining statically typed Receivers are matched exactly against `(Receiver type, name)` in the registry. A Receiver is not normalized twice, and positional argument counts and types are checked. Unregistered names, keyword arguments, unpacking, general overload inference, implicit type conversion, and executing arbitrary Python implementation methods are rejected. `convert(intrinsics=...)` can supply an explicit provider table to the Frontend; Realization remains independent and no new recipes are added to standard C/Python Packs.

title: Registry matching of typed intrinsics and restricted Frontend normalization

level: MUST

related: [CST_066](construct.md#cst_066)

## FRT_064

If a provider explicitly registers several signatures under one key in `IntrinsicRegistry`, the Python Frontend filters candidates strictly by the constructed Receiver and positional argument types and builds `IntrinsicCall` only for exactly one matching signature. The Receiver and arguments are not normalized again for each candidate. With one candidate, types derivable from the known Receiver can be used as expected types when constructing expressions. With multiple candidates, no expected type is guessed, and expressions that require a contextual type are rejected if none is available. Type-variable binding is limited to matching types explicitly represented within a signature: there is no type promotion, candidate ranking, or general Python type inference. The selected signature determines the return type statically, while existing precedence of user declarations over provider registrations is retained. An expression statement calling a typed intrinsic method with a `None` return type can also be constructed, but standard Python/C Packs do not gain new Realizations.

title: Unique static selection among signatures and signature-local type variables

level: MUST

related: [CST_067](construct.md#cst_067)

## FRT_065

By default, `PythonFrontend()` uses `standard_intrinsics()`, normalizing zero-argument `str()`, `int()`, and `float()`, one-argument conversions with explicitly typed `int`/`float`/`str`/`bool` input, and `upper()`/`lower()` on statically typed `str` Receivers into `IntrinsicCall` with selected `IntrinsicDefinition`. Types before and after conversion and individual obligations are determined by provider declarations under CST_068; input Values are not executed, and conversion exceptions or Unicode case expansions are not guessed. Specifying `intrinsics=IntrinsicRegistry(...)` replaces the default table; `standard_intrinsics().extend(...)` permits explicit extension. The precedence of same-named user declarations and existing mapped names/classes, rejection of ambiguous candidates, and rejection of keyword/unpacked arguments remain unchanged. Multiargument `int(str, base)`, unregistered types or methods, dynamic conversions, and formatting are not admitted. No corresponding Intrinsic recipes are registered in standard Python/C Target Packs at this stage: constructibility is distinct from the ability to produce output.

title: Static normalization of standard conversions and Unicode string operations

level: MUST

related: [CST_068](construct.md#cst_068)

## FRT_066

From Python AST `ast.JoinedStr`, the Frontend creates `FormattedString` composed of literal fragments and typed `str(x)` `IntrinsicCall` fragments. Each interpolated expression is normalized once, with a static resolution of the `str` signature from the standard or explicitly supplied `IntrinsicRegistry`. Only `!s` and default conversion are admitted; `!r`, `!a`, format specifications, unregistered types, and ambiguous stringification are rejected. `print()` with no arguments, multiple positional arguments, or one `int`/`float`/`bool`/`str` argument becomes `PrintValues`, with each value normalized through the same typed stringification signature. A legacy single-string `print(str_value)` remains a `Call` to preserve compatibility with old Packs. Dynamic `sep`/`end`/`file`/`flush`, unpacked or keyword arguments, and arbitrary object printing are rejected. Values are not evaluated or formatted while parsing; no new Realizations are required of the Python/C Packs.

title: Static normalization of restricted f-strings and typed print

level: MUST

related: [CST_069](construct.md#cst_069)

## FRT_068

For binary `in`/`not in` comparisons, the Python Frontend normalizes the left expression first and the right expression second, exactly once each. If the right side is a typed List or Dict, it constructs `Membership` from CST_071, rejecting mismatched element or key types. If the right side is a String, it retains the existing `StringContains`. Unsupported right-side types, nested dynamic containment protocols, and comparison chains involving membership are rejected. No new Python/C Pack recipes are registered in this step.

title: Static normalization of typed List/Dict membership tests

level: MUST

related: [CST_071](construct.md#cst_071)

## FRT_067

The Python Frontend normalizes `ast.Assign` into one `UnpackAssign` only if its single target is a parenthesized or unparenthesized fixed-length tuple consisting entirely of previously declared ordinary typed names. The right-hand side is normalized once; element counts and assignment types are checked from its static `tuple[T1, ...]` shape. `a, b = b, a`, assignment from tuple variables with different element types, and repeated targets are permitted. Implicit declarations of new names, nested/starred/list/attribute/subscript unpacking targets, chained assignment to multiple targets, mapped-object rebinding, and unknown tuple shapes are rejected. Existing Symbols are not recreated after assignment, and the Frontend does not generate Target temporaries. Python/C Packs are not required to provide a corresponding recipe.

title: Fixed-length tuple unpacking into previously declared names

level: MUST

## FRT_069

The Python Frontend normalizes an `ast.Slice` in `ast.Subscript` into `SliceValue` only when the target is a typed `list[T]` or `str`. The target is normalized once; present start, stop, and step expressions are each normalized once in source order. Every specified bound must be a Value of known integer type; `bool`, `float`, and unresolved names are rejected. Missing bounds are not filled with zero or length. In particular, `s[::-1]` and `s[0::-1]` produce different Models. A literal zero step remains represented as a runtime `ValueError` contract. Existing single-index reads, List/Dict updates, and static tuple indexing do not change. Dictionary, tuple, or nonsequence slicing and slice assignment are unsupported. Adding Target Pack recipes is not required.

title: List/string slice normalization preserving omissions

level: MUST

related: [CST_072](construct.md#cst_072)

## FRT_070

When the single name in `for name in source` is absent from the current declaration table, a new typed Symbol is introduced at the iteration entry only if exactly one static element type can be determined. Admitted sources are integer `range`, strings, `list[T]` with known element type, and nonempty fixed-length tuples whose element types are all identical. Mixed-type tuples, empty tuples, Iterables of unknown shape, dictionaries, reserved names, and non-iterable values cannot introduce variables implicitly. The source expression is normalized once in the pre-introduction name environment. The new Symbol may be referenced or reassigned only within the loop body; references from `else` or after the loop are rejected under the current admission limits. This does not claim that Python `if` or `for` creates a new lexical scope: it is a Frontend restriction avoiding analysis of possibly unbound variables. A loop variable declared beforehand retains its existing Symbol and may be referenced after the loop. There is no fabricated initialization for empty iteration, per-iteration new Symbol, general definite-assignment analysis, or dynamic type inference. The Model retains the introduction distinction from CST_073; Target Packs need not support the new binding.

title: Restricted implicit introduction of for variables with known element types

level: MUST

related: [CST_073](construct.md#cst_073), [CST_004](construct.md#cst_004)

## FRT_071

Within the bodies of `if`/`else`, `while`/`else`, `for`/`else`, and `with`, an `AnnAssign` declaring a new ordinary value name with an explicit type and initializer is admitted as `Initialize`. Each declaration stays at its execution position in the original `Block`. Only later references/reassignments in the same body, or in control bodies nested inside it, are admitted. References to newly declared names from another branch, a loop's `else`, or after the body are rejected even if Python might bind them, because general path-dependent initialization is not analyzed. This is a restriction on admissible reference positions, not a new Python lexical scope: Symbol ownership paths remain those of existing functions or the module. Existing declared names remain referable and reassignable as before. Capturing a new control-local name or FRT_070 loop variable in a lambda is rejected because its binding lifetime could outlive the body. Function declarations inside control bodies, mapped-object declarations/rebinding, new names directly inside `try`/`except`/`finally`, generic cross-scope alias initialization analysis, and unannotated implicit declarations are not added. No new Constructs or Target recipes are introduced: existing `Block`, `Initialize`, and `Symbol` are reused, with no new semantic-support declarations in standard Packs.

title: Typed value declarations confined to a control-flow body

level: MUST

related: [CST_002](construct.md#cst_002), [CST_003](construct.md#cst_003), [CST_073](construct.md#cst_073)

## FRT_073

The Python Frontend admits explicit typed top-level definitions `def f(a: T, *rest: U) -> R:` and definitions with no fixed parameters, `def f(*rest: U) -> R:`. `U` must be a statically known ordinary Value type; within the function `rest` is bound to one immutable Tuple Symbol of type `tuple[U, ...]`. Fixed parameters, trailing immutable-literal defaults, zero or more explicit positional arguments, and keyword binding of fixed parameters are checked for types, duplicates, and missing values. Argument expressions normalize exactly once in source order, with reordering to the binding order of fixed parameters recorded in existing `evaluation_order`. Existing compatible `len(rest)`, `sum(rest)`, and iteration `for item in rest` with homogeneous element type are admitted. Variadic tuple annotation `tuple[T, ...]` is distinguished from fixed-length Tuple and accepts assignment from a compatible fixed-length Tuple value. At this stage, subscripting variadic tuples, static unpacking of them, dynamic call unpacking outside `def` such as `f(*rest)`, `**kwargs`, keyword-only parameters, variadic parameters of methods or nested functions, and treating variadic functions as first-class function values are rejected. No new C Target Realization rule for functions or variadic tuples is added; explicit Admission support by the Target is required.

title: Statically typed variadic positional parameters of user-defined functions

level: MUST

related: [CST_074](construct.md#cst_074), [CST_017](construct.md#cst_017)

## FRT_072

Only `global name[, ...]` declarations grouped at the beginning of a top-level typed `def`, immediately after any docstring, are accepted. Each name must denote an ordinary `ValueType` variable already initialized with a type at module top level before the function definition. Unknown names, later module declarations, mapped types, collisions with parameters, repeated global declarations, typed redeclaration within the same function, and collisions with function names are rejected. The global declaration affects name binding throughout the function scope and adds no executable Construct. Reads and simple `name = value` assignments to declared globals normalize to `Reference`/`Assign` pointing to the original module `Symbol`, retaining existing type compatibility and initialization rules. Scalar augmented assignments to integer/float globals such as `name += value`, as admitted by FRT_060, likewise become `AugAssign` pointing to the same original Symbol, preserving `target_once`, `read_before_rhs`, and `rebind` semantic contracts. Reassigning module variables from an ordinary function requires explicit `global`; without it, an augmented-assignment target is treated as a local binding throughout the function, and undeclared or uninitialized locals are rejected rather than falling back to an outer scope. Assignment to existing declared names inside a conditional is permitted, but a `global` statement inside a control body or in the middle of a function is not. `global` inside nested functions or methods, `nonlocal`, use of global names as `for` targets or typed redeclarations, implicit creation of new module names, and other unsupported Python binding syntax are rejected. Nonscalar augmented assignments such as those on strings and lists remain rejected under FRT_060. `Symbol.scope == ()` and declaration-object identity are preserved; no Python-specific Global Construct is introduced. Correct Target storage of shared state and the side effects and order of function calls are separate obligations; unsupported C Targets continue to fail.

title: Restricted explicit global rebinding of already declared module variables

level: MUST

related: [CST_002](construct.md#cst_002), [CST_003](construct.md#cst_003), [CST_017](construct.md#cst_017)

## FRT_074

The Frontend separates a top-level `def __pyinto_runtime__():` from the AST before normalization. It does not include that function in the Construct Model and does not normalize or validate syntax inside its body. The hook must be a single, synchronous, zero-argument, undecorated function definition. Duplicate definitions, an identically named class, async function, direct assignment, or a definition with decorators or arguments are rejected. `PythonFrontend.parse()` also excludes this function. All other source declarations remain subject to the ordinary Frontend acceptance rules; the exclusion does not relax type or name-resolution contracts for the rest of the source.

title: Static separation of the runtime magic function

level: MUST

## FRT_075

Kind words are recognized statically only when imported with `from pyinto.kinds.<surface>.<tier> import word [as alias]`. The surfaces are `datatypes` / `memory` / `declarations` and the tiers `general` / `detailed`; each module provides a fixed set of words. A word not in that module, the `import pyinto.kinds...` form, imports from `pyinto.kinds` or one of its surfaces, collisions with builtin type names, and duplicate aliases are rejected. In type positions, `Wide[X]` / `Narrow[X]` / `Unsigned[X]` take the Python-side shape of `X`, `Size` / `Index` / `Byte` / `Int[N]` / `UInt[N]` / `CodeUnit[N]` / `Pointer[T]` / `Enum[T]` of `int`, `Float[N]` / `Decimal[N]` of `float`, `Char` of `str`, `Array[T, N]` and `Buffer[T]` of `list[T]`, `Function[[...], R]` of `Callable[[...], R]`, `Void` / `Nil` / `Null` of `None`, and `Ref[T]` / `Owned[T]` / `Shared[T]` the same shape as `T`, each with a label exactly as written. Sizes and lengths accept only positive integer literals; the Host does not fix any range. Annotations whose argument count or kind does not fit the word's form are rejected.

title: Importing kind words and type annotations

level: MUST

## FRT_076

`Void` / `Nil` / `Null` in value positions normalize to `NoneAlias` and may be used only when assigned to labeled declarations or arguments, or in `==` / `!=` comparisons with labeled values (`NoneAliasComparison`). `Pointer.address(x)` accepts only a bare variable name and normalizes to `AddressOf`; `Pointer.load(p)` takes a `Pointer[T]`-typed value and normalizes to `PointerLoad`; `Pointer.store(p, v)` as a statement normalizes to `PointerStore`. Keyword or unpacked arguments, wrong argument counts, unknown operation names, and `Pointer.store` inside an expression are rejected. Using a type word as a value is also rejected.

title: Normalizing None-alias values and pointer operations

level: MUST

## FRT_077

The initializer of a `Ref[T]` variable, and each argument (including defaults) bound to a `Ref[T]` parameter, must be a bare variable name that is not a mapped object (`Reference`). Expressions and literals are rejected. Later assignments follow the ordinary assignment rules; what writing to or rebinding a `Ref` means is up to the Target.

title: Requiring variable names where Ref types are bound

level: MUST

## FRT_078

A module-level class definition may carry the `pyinto.kinds.declarations.detailed` decorators `@Interface` / `@MixIn` / `@Implements(...)` in any order, in addition to at most one registered class decorator. `Interface` and `MixIn` take no arguments; `Implements` takes one or more names of classes defined earlier in the same module. The class's own name, undefined or later classes, keyword arguments, duplicate words, and type words used as decorators are rejected. These decorators do not relax class acceptance rules (an explicit `__init__`, single inheritance, and so on).

title: Kind class decorators

level: MUST

## FRT_079

An Interface Mapping mapped object is created only by an argument-free `Class.variant()` call. Positional, keyword, and unpacked arguments are rejected, and no numeric range or size is accepted as part of the mapped-object shape. Registered constructors have the form `(Symbol) -> Construct`.

title: Argument-free mapped-object constructors

level: MUST

## FRT_080

`Memory.new(T, value)` / `Memory.new_buffer(T, length, value)` / `Memory.length(h)` / `Memory.borrow(h)` normalize as values, and `Memory.release(h)` / `Memory.resize(h, length)` / `Memory.copy(destination, source)` / `Memory.fill(h, value)` as statements. `T` is read with the same rules as type annotations. The target of `resize` must be a bare variable name. Mismatched value types, missing ownership or `Buffer` labels, non-integer lengths, wrong argument counts, keyword or unpacked arguments, unknown operation names, statement operations inside expressions, and `Memory` used as a type are rejected. The result of `Memory.new` carries the `Owned` label but may also be assigned to a variable declared `Shared`; the ownership kind is read from the declaration.

title: Normalizing dynamic-memory operations

level: MUST
