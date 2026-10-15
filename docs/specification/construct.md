# Construct Model

This document states the implemented Construct Model contracts for pyinto. The [Japanese canonical document](../../devdocs/canonical_documents/specification/construct.md) is authoritative. This English translation retains every clause, its complete operative conditions and qualifications, its normative level, and any cross-references. It does not imply that every Target can realize every Construct.

## CST_001

Constructs retain normalized operations and named child parts, not Python AST nodes. `parts()` maps part names to their values; `variant()` is a structural discriminator used when selecting a Realization rule. The Construct itself must not implement output generation via `emit()`.

title: Normalized structure and named child parts

level: MUST

## CST_075

`variant_domain()` exposes the known finite domain as `frozenset[str]`, or `None` when it cannot be enumerated. A Construct whose `variant()` method is not overridden has domain `{"default"}`. Built-in Constructs overriding it must enumerate concrete choices in `VARIANTS`, unless the domain is open (`VARIANTS=None`) because providers can register more keys, as with `IntrinsicCall`. An external Construct overriding `variant()` without declaring `VARIANTS` also has an unknown domain. The domain is Model metadata independent of any Target or artifact format and supports validation at Realization registration time.

title: Public domain metadata for Construct variants

level: MUST

## CST_002

Every newly declared value-bearing `Symbol` must retain its annotated type. An ordinary value declaration has exactly one recursive `ValueType`; a mapped object instead has `MappedType`, distinguishing its source and variant. `MappedType` holds no constructor arguments and no numeric range or size. Builtin-only Symbols use `type=None`. The `kind` and type-shape accessors are derived from `type`, not separately stored fields. Do not silently reinterpret mapped objects or builtin-only Symbols as ordinary `ValueType` instances, and do not determine Target-specific type spellings from Python annotations.

title: Preserving types and mapped object shapes

level: MUST

## CST_003

A `Block` retains ordered child Constructs. `Branch` and `While` retain conditions and bodies; only a present `else` Block becomes a named part, and in that case `variant()` is `with_else`. `Break` and `Continue` remain distinct Constructs.

title: Block, branch, and loop structure

level: MUST

## CST_004

`For.parts()` exposes only its `IterationEntry` (binding destination and iterable), body, and an optional else Block. `Range` retains its original one to three integer arguments; `bounds()` supplies the Python `range` defaults of start `0` and step `1`. A `For` does not expose Target-oriented start, stop, or step output Slots.

title: Model contracts for iteration entries and range

level: MUST

## CST_005

`With` requires at least one ordered `ContextEntry` and a body `Block`. Each entry contains a context expression and optional binding destination. The mere ability to represent these parts does not establish that a given Target can preserve the context manager's exit behavior.

title: Separation of context structure from realizability

level: MUST

## CST_006

Neither `Program` nor any other Construct exposes conversion methods such as `to_source()` or `to_c()`. The Model neither imports nor depends on Realizations, Target Packs, or code emission; conversion is initiated through `pyinto.convert()` and `pyinto.realize()`.

title: Separation of Model from conversion entry points

level: MUST

## CST_007

Basic `parts()` implementations must expose Target-independent `Identifier` values for names, `Symbol` for type references, and tuples for ordered children. They must not manufacture Realization-only `Name`, `TypeName`, `Joined`, or `Requirements` objects. Output requirements do not become part of the Program Model.

title: Separation of Model parts from output-layout helpers

level: MUST

## CST_008

`With` exposes ordered entries as dynamically named children `entry0`, `entry1`, and so forth. Neither source delimiters nor newline formatting are prescribed by the Model; Realization decides both.

title: Pure structural expansion of With entries

level: MUST

## CST_009

Only `entry`, `body`, and, if present, `otherwise` are published by `For.parts()`. A Realization must arrange any Target-dependent `target/start/stop/step` Slot expansions; a `For` whose iterable is not a `Range` is still a valid Model value.

title: For independent of a particular iteration form

level: MUST

## CST_010

`Program` names only its actual source `body` as a Model part. No output-oriented `requirements` belongs in `parts()` or the class's `HOLES` declaration; Composition supplies that output Slot independently.

title: Boundary between Program structure and output requirements

level: MUST

## CST_011

Accept only values whose exact Python type is `int` or `str`: exclude `bool` despite its Python inheritance from int, and exclude float, `None`, and all other types at Model construction time. Integer range restrictions and Target string spelling belong to Realization.

title: Accepted Model value domain for Literal

level: MUST

## CST_012

A Construct tree created by `PythonFrontend` is inspectable without selecting a Target Pack and does not retain Python AST nodes or generation-only Layout objects. Applying multiple Target Realizations to one Model must leave that Model unchanged as a usage contract; this does not require an enforced read-only wrapper.

title: Independent Model inspection and reuse

level: MUST

## CST_013

The legacy class declaration `Construct.HOLES` enumerates names that a class may statically expose, not Slots every Template must use. `parts()` exposes only names actually present on an instance. Dynamic numbered names may be declared by `accepts_part_name()`; attempting to compose a nonexistent part is rejected. Output-only Slots do not belong to Model declarations.

title: Model part names versus output Slots

level: MUST

## CST_014

Validate operand/operator types for `Comparison`, assignment compatibility in `Initialize` and `Assign`, and Boolean condition types in `Branch` and `While` when the Construct is created. Raise `ConstructError` for invalid Models rather than postponing checks until Realization selection or `parts()`. Inspecting `parts()` of a valid instance must not make Target-dependent decisions.

title: Construction-time Model invariants

level: MUST

## CST_015

`Arithmetic` retains two integer Values in order and operators `+`, `-`, `*`, `//`, `%`, plus the bitwise operators specified by CST_065. `IntegerUnary` retains an integer operand and unary `+`, `-`, or `~` (CST_065). Reject type/operator mismatches during Model construction, without constant folding or Target-specific division/remainder rewrites.

title: Target-independent integer arithmetic operations

level: MUST

## CST_016

`BooleanOperation` retains an ordered tuple of at least two Boolean Values and `and` or `or`; `BooleanNot` contains a Boolean operand. Both validate type and structure at construction. The Model performs no evaluation; Realization must preserve left-to-right order and short-circuit semantics.

title: Boolean ordering and short-circuit preservation

level: MUST

## CST_017

The signature stores a single `return_type: ValueType` rather than duplicating the return kind and composite type shape. Each `Parameter` exposes its name and type, and `FunctionDefinition.parts()` exposes `return_type` as the recursive `ValueType` itself. Return checking covers the definition's body, nested Branch/loop/With/Try bodies, handlers, else and finally; it excludes nested FunctionDefinitions and expression-level LambdaValues, whose returns belong to those definitions. Duplicate parameter names, malformed signatures, and explicitly incompatible return expressions fail at construction. The Model neither proves that all control-flow paths return nor selects a Target's calling convention or type syntax.

title: Typed function signatures and definition structure

level: MUST

## CST_018

The `FunctionCall` retains a resolved signature and each argument in order, with arity and type checked at construction. `FunctionDefinition` matches non-None return expressions using ordinary assignability, including nominal derived-to-base instance compatibility. For `-> None`, allow only bare `Return()` or an explicit `NoneLiteral`; an `Any`/`object` return accepts a broad set of values but not a valueless Return. `None` is an explicit `ValueKind.NONE`, not a result of evaluating or optimizing the Model.

title: Normalization of return values and function calls

level: MUST

## CST_074

This facility applies to statically typed `*args: T` on user-defined top-level functions. `FunctionSignature.variadic_parameter` is one `Symbol` with `ParameterRole.VARIADIC` and a recursive `ValueType(TUPLE)` whose `TupleType(variadic_element_type=T)` is distinct from both a fixed-length Tuple and a List or a single T value. A homogeneous variadic Tuple contains zero or more immutable elements and has type notation `tuple[T, ...]`; a fixed Tuple whose every element is assignable to T may be assigned to a variadic-Tuple variable. Variadic Tuple values must not be mistaken for fixed Tuple values in static indexing or unpacking. `FunctionDefinition.parts()` exposes fixed parameters through `parameters`, adding a separate named `variadic_parameter` only when present; references in the body resolve to the same Tuple Symbol. A direct `FunctionCall` binds declared fixed parameters first, and retains surplus positional argument Values individually, in source order, while checking type, count, source evaluation order and omitted defaults. Target Realization must bind those surplus values into *one immutable Tuple* in the function body and satisfy both `function.variadic.tuple_binding` and `call.variadic.tuple_binding` Admission contracts. The Model chooses no Target ABI, array layout, or unpacking strategy. Do not project these functions into fixed-arity `CallableType`: currently only direct calls are supported.

title: Typed user-defined variadic arguments and runtime Tuple binding

level: MUST

## CST_019

Nested functions appear recursively as existing `FunctionDefinition` nodes in `Block.children`; there is no special nested-function Construct. `FunctionSignature.scope` identifies the declaration's lexical ownership path, `Symbol.scope` identifies the binding's ownership path, and they distinguish different bindings that share a name. `FunctionCall.signature` and `Reference.symbol` retain resolved links to the original declarations; none of this imposes Target names or storage for captured variables.

title: Recursive nested-function structure and binding origins

level: MUST

## CST_020

A function's `CallableType` contains ordered positional argument `ValueType`s and one return `ValueType`, recursively embedded in `ValueType`. Reject missing function shapes and function shapes attached to nonfunction types during construction. Function type compatibility uses exact structural shape equality rather than arbitrary Python Callable subtyping. A regular `Value` exposes `kind` and function/tuple/list/dict/instance shapes from one `value_type`; only scalar values may derive a `ValueType` from the existing value kind. Do not maintain independent competing representations of composite type shapes, and do not require ordinary `ValueType` for mapped-object references. Extend existing Initialize/Assign/FunctionCall compatibility checks for function-valued variables and arguments.

title: Structural types and compatibility for first-class functions

level: MUST

## CST_021

`FunctionSignature` remains the declaration identity used for direct calls. A fully typed signature exposes a stable `value_symbol` identifying the same declaration, with `ValueKind.FUNCTION` and matching `CallableType`. The existing `Reference` can denote a declared function or function-typed variable, and a `FunctionCall` returning a function type propagates its `CallableType`. A runtime function value instantiated by each nested-function execution is not the same thing as the static declaration; environment storage and runtime identity are not fixed by the Model. Signatures with mapped-shaped parameters retain direct-call behavior but cannot become function values. Return annotations require `ValueType`; do not infer undefined mapped returns.

title: Separating function declarations from function-value references

level: MUST

## CST_022

Unlike the direct-declaration-bound `FunctionCall`, `FunctionValueCall` keeps a `callee` expression of `ValueKind.FUNCTION` with complete `CallableType`. It validates argument arity, explicit types and nested callable shapes at construction; nominal instance parameters accept derived-to-base assignment. Nested Callable/List/Dict/Tuple shapes continue to require strict equality, not inferred variance. `parts()` exposes `callee` and the present dynamically numbered `arg0`, `arg1`, etc.; `accepts_part_name()` recognizes such names. Realization must evaluate `callee` exactly once *before* any argument, then each argument once in written order. The call's `kind` and `callable_type` follow the callee's return type. Closure allocation, storage, and Target calling conventions remain unspecified.

title: Structure and validation of first-class function-value calls

level: MUST

## CST_023

Direct closure dependencies are readable from `FunctionDefinition` bodies, `Reference.symbol`, direct-call `FunctionCall.signature`, and lexical `scope`. `pyinto.analysis.lexical_captures(definition)` is a non-mutating, Target-independent projection: it returns distinct Symbols declared in strictly enclosing *function* scopes that this definition references directly, in first-use order and retaining declaration identity. Direct calls to nested functions declared outside this function and references to their function values use their original `value_symbol`. Nested child-function bodies are not traversed when computing the parent's direct captures. Module declarations, the function's own locals/parameters, and self recursion are excluded. No special Closure Construct is added.

title: Derivation of direct lexical captures from existing declarations

level: MUST

## CST_024

Static `Symbol` and `FunctionSignature` declarations do not themselves represent the runtime values or environments created at every invocation. Even if several factory calls share the same nested declaration, returned functions must refer to their respective environments; mutable captured bindings may be shared correctly, remain valid after the outer call exits, and be passed with indirect calls. Realization must decide whether it can guarantee these properties and explicitly reject otherwise. `lexical_captures` projects only *direct* captures; it does not infer transitive retention needed by further nested functions, escape, lifetimes or allocations.

title: Separating static declarations from per-invocation closure environments

level: MUST

## CST_025

`TupleType` carries ordered immutable per-position `ValueType` shapes, recursively embeddable in `ValueType`, Symbol, parameter and return types. Reject a Tuple type lacking its shape and a Tuple shape on a non-Tuple type. `TupleValue` retains its unexecuted Value expressions in written order, including the empty Tuple. Distinct element types or lengths are explicit mismatches; do not infer arbitrary Python tuple covariance or coercion. Extend initialization, assignment and function passing checks to accept only matching shapes.

title: Fixed-length Tuple shapes and ordered values

level: MUST

## CST_026

At construction time require a Tuple-typed source Value and a static nonnegative integer index within its fixed length. The result's `kind` and recursively nested `callable_type` / `tuple_type` derive from that indexed element type. `parts()` exposes the original expression as `source` and the index as `index`. Realization evaluates `source` once and extracts the item, without leaking Target Tuple representation into the Model. Variable-length or dynamic indexing, negative indices and indexed assignment are not defined in this stage.

title: Fixed-position Tuple element access and evaluation

level: MUST

## CST_027

`Raise` records a statically named supported builtin exception and an optional message expression of string Value type. The supported names are exactly `ValueError`, `TypeError`, and `RuntimeError`, checked at construction. Omitted and supplied messages are distinct, and the Model never evaluates the message expression. `parts()` exposes an `Identifier` at `exception` and the original message Value only when given. There is no general Python exception-object type system, arbitrary class construction, or exception-attribute access.

title: Raising the supported builtin exceptions

level: MUST

## CST_028

An `ExceptHandler` holds a nonempty, unique, ordered tuple of supported exception class names and a body Block. `Try` holds a mandatory body Block, ordered handlers, optional `else` Block for normal completion, and optional `finally` Block. Require at least one handler or `finally`, and allow `else` only with a handler. `parts()` exposes `handlers`, `otherwise`, and `final` only when present. Its `variant()` distinguishes the presence of handler and finally clauses.

title: Ordered exception handlers and Try invariants

level: MUST

## CST_029

Only exceptions raised in the `try` body are matched to handlers, in declaration order, with the first matching type selected; unmatched exceptions propagate. `else` runs only when the try body ends normally, without an exception, `return`, `break`, or `continue`. `finally` executes on *every* exit path, including normal completion, exceptions, and control transfer; control transfer originating in `finally` can supersede an earlier transfer according to Python rules. Realization is responsible for Target exception-type matching, propagation and finally behavior, and must reject when unable to preserve them. Existing With-specific special-method, exit and exception-suppression contracts remain unchanged.

title: Exception propagation, else, and finally control flow

level: MUST

## CST_030

`ValueKind.LIST` and `ListType` fix one recursive element `ValueType` but not the runtime length, and that type flows through Symbols, function signatures, callable shapes and nested Tuples. `ListValue` retains element Values in order and validates their matching structural element types; explicitly typed empty Lists are valid. A second binding via `Reference` aliases the same mutable List, so the Model does not pre-evaluate or duplicate it. Initialization, rebinding, and argument passing extend the existing compatibility checks but do not infer arbitrary list covariance or coercion. Storage and runtime identity are Target responsibilities.

title: Typed mutable homogeneous Lists

level: MUST

## CST_031

`ListElement` stores a List-typed source and integer-typed index expressions, propagating the element's `kind` and recursive Callable/Tuple/List type shape. `ListElementAssign` stores a `Reference` to an existing List variable, an index Value, and a type-compatible RHS Value; it is mutation, not variable rebinding via `Assign`. Constructors validate source/index/element types but do not evaluate them. Realization must preserve expression order, exactly-once evaluation, Python negative-index and out-of-bounds behavior, and mutation visible through aliases, or explicitly reject. Runtime List length and memory layout are not determined by the Model.

title: List element access, mutation, and aliases

level: MUST

## CST_032

`ValueKind.DICT` and `DictType(key_type, value_type)` retain two recursive `ValueType`s: the key type must be *exactly* `int` or `str`, while the value is any currently permitted explicitly typed shape. Shape information propagates through Symbols, signatures, Callables and nested containers. `DictValue` stores ordered `DictEntry(key, value)` expressions, enforcing key and value compatibility at construction; an empty Dict requires an explicit type shape. Evaluate every key expression then its value expression once, in entry order. A later equal key updates its value without changing the key's first insertion position. Aliases share the same mutable dictionary. No Python hash-table implementation or Target storage scheme is specified.

title: Typed mutable Dictionaries and ordered construction

level: MUST

## CST_033

`DictElement(source, key)` retains a Dict expression and type-compatible key, propagating the value's kind and recursive Callable/Tuple/List/Dict shapes; reading a missing key raises runtime `KeyError`. `DictElementAssign(target, key, value)` retains a dictionary-variable Reference and typed key/value expressions, representing existing-key updates or new-key insertion. Updating retains key position; insertion appends it. Constructors check dictionary/key/value types but perform no evaluation. Realization must support one-time ordered evaluation, failed lookup, insertion order and alias-visible mutation or explicitly reject. `KeyError` is *not* thereby introduced as a general Model exception value or catchable exception type.

title: Dictionary element lookup, insertion, update, and failure

level: MUST

## CST_034

`InstanceType(name, scope)` is nominal: independently declared classes remain distinct even with identical structural shapes. Nominal identity propagates recursively through `ValueType`, Symbols, signatures, Callables and Tuple/List/Dict elements. `ClassSignature` stores an `InstanceType`, ordered `FieldDefinition`s and method `FunctionSignature`s, and requires typed `__init__`. `ClassDefinition` reuses existing `FunctionDefinition` bodies and checks agreement with declarations. The Model does not represent Python's dynamic class/metaclass machinery or Target storage.

title: Nominal instance types and static class declarations

level: MUST

## CST_035

For an ordinary instance method, the receiver is a Symbol of `ParameterRole.RECEIVER` with `ValueKind.INSTANCE` and the owning class `instance_type`. `FunctionSignature.receiver` explicitly identifies that parameter, distinct from `ParameterRole.ORDINARY`; `Reference` points to the same declaring Symbol. No magic attaches to the spelling `self`, and Realization must not infer receiver identity from name or position. Target representation as explicit argument, object or pointer is left open.

title: Explicit instance method receivers

level: MUST

## CST_036

`InstanceCreation` records the nominal class and argument expressions and requires allocation of a *fresh* instance followed by its declared `__init__`. Typed reference assignment/rebinding shares that instance rather than copying it. `FieldInitialize` establishes an explicitly typed field during initialization; `FieldRead`/`FieldWrite` relate a defined field to an instance Value. `MethodCall` separately stores an evaluated receiver expression, statically resolved method signature, and explicit arguments, requiring receiver evaluation once before arguments are evaluated left to right. Type/method/field consistency is checked during Construct creation. Memory lifetime, attribute layout, method ABI and generated code belong to Realization.

title: Instance creation, fields, and method-call obligations

level: MUST

## CST_037

Static single inheritance is stored as a direct link to the declared base class through both `InstanceType.base` and `ClassSignature.base`; arbitrary depth uses repeated links, not depth-specific Constructs. Derived and base nominal types remain distinct. `InstanceType.is_subtype_of()` follows only declared ancestry. Derived-to-base assignment, argument passing and returns are supported; reverse conversion is not assumed. Do not introduce blanket covariance/contravariance for Tuple/List/Dict/Callable shapes. `resolve_field()` and `resolve_method()` return the signature from its defining class rather than copying members into the derived declaration.

title: Static single inheritance and nominal derived types

level: MUST

## CST_038

`MethodCall` preserves its receiver, resolved signature, argument expressions, and static receiver class, while explicitly storing `MethodDispatch.VIRTUAL` or `.SUPER` with `lookup_start`. A normal VIRTUAL call selects the closest overriding method on the *runtime* class along the declared ancestry; the Frontend must not presume that runtime class. SUPER begins lexically immediately above the class defining the current method and directly resolves its signature, passing the *same* receiver instance. Explicit parent `__init__` calls fall under SUPER. Dispatch tables, Template/Slots and ABI are Realization choices.

title: Explicit virtual and super method dispatch

level: MUST

## CST_039

A derived class declares its own fields/methods separately and can access inherited fields with their defining class recorded. A field/method name conflict in the inheritance hierarchy is rejected. Overrides other than `__init__` must exactly match explicit positional parameter and return type shapes; general Python variance is not inferred. FieldRead/FieldWrite and MethodCall check declaration ownership and receiver subtype relationships. Aliasing and dispatch by the receiver's runtime class remain Realization obligations, not executed by the Model. No class Target Realization is registered at this stage.

title: Inherited fields and method override contracts

level: MUST

## CST_040

Nominal identity and declaration ownership must survive References, parameters/returns, TupleElement/ListElement/DictElement, and lexical captures. A base-typed Reference may hold a derived instance; virtual MethodCall retains the signature resolved from its static receiver type, without assuming the instance's runtime type equals it. Field mutation is distinct from rebinding names, and instances continue to share reference identity. Nested Tuple/List/Dict/Callable shapes keep their exact matching rules, rather than acquiring blanket variance.

title: Composing inheritance with existing value structures

level: MUST

## CST_041

An explicitly declared function-typed instance field can be read as a function value using `FieldRead` and invoked with `FunctionValueCall(callee=FieldRead(...), arguments=...)`. Unlike ordinary MethodCall, this has *no implicitly bound receiver*. Inherited fields retain the original defining class as `FieldRead.owner`. Evaluate the callee expression exactly once before positional arguments, each in order, as required by FunctionValueCall. No additional Construct or Target class ABI is introduced.

title: Function-valued fields and indirect calls

level: MUST

## CST_042

`BooleanLiteral(value: bool)` must accept only exact Python bool (`type(value) is bool`), not rely on bool's int ancestry, and retain the immutable constant as `ValueKind.BOOLEAN`. It leaves strict int/string Literal and pre-existing Boolean short-circuit contracts unchanged. `variant()` returns `true` or `false`; the Target spelling is supplied by Realization.

title: Boolean constant Values distinct from integers

level: MUST

## CST_043

`NoneLiteral()` represents the singleton Python `None` as an *expression* of `ValueKind.NONE`, not an omitted optional Model field such as `Return.value is None`. It may pass through initialization, rebinding, arguments and returns where an existing `object` / `Any` value is compatible; it does not introduce general None-typed variables or Optional/Union types. In `-> None` functions, both `return None` and bare `return` normalize to the existing `Return()`. Keep Literal's former accepted domain and the restriction against None as a collection element.

title: Structural distinction between None values and omission

level: MUST

## CST_044

`ConditionalExpression(condition, when_true, when_false, result_type)` stores a Boolean condition and independent true/false expressions as ordered child Values, with an explicit recursive result `ValueType`. Validate *both* branches' assignability to that type at construction. At runtime evaluate the condition once and *only* the selected branch once; never evaluate an unselected branch. The Frontend neither pre-executes branch side effects/exceptions nor picks a branch. Realization chooses Target branching and value representation. No automatic Union of differing branch types is added.

title: Typed conditional expressions and unselected branches

level: MUST

## CST_045

`Length(operand)` is an integer-valued operation on statically typed str, fixed Tuple, mutable List or mutable Dict only. No `object`/`Any` or arbitrary `__len__` inference. Evaluate the operand expression once, even when Tuple length is known from its type. String length counts Unicode code points, Dictionary length counts distinct keys, and List length reflects the element count at call time. Target representation and length-retrieval strategy belong to Realization.

title: Length of typed containers and strings

level: MUST

## CST_046

`Absolute(operand)` is an integer Value requiring `ValueKind.INTEGER` at construction. Evaluate the operand exactly once and obtain the mathematical absolute value; neither Model nor Frontend precomputes it. Realization determines whether the Target integer range can represent the result. Exclude floats, complex numbers, bool-as-int, and user-defined `__abs__`.

title: Narrowly typed integer absolute value

level: MUST

## CST_047

`Extremum(operation, operands)` stores `min` or `max` and at least two ordered integer Values, each evaluated exactly once in written order for integer comparison. Exclude the single-iterable overload, `key=` and `default=`, heterogeneous or arbitrary-object comparison, general Python special methods, and keyword or unpacked arguments. The Model does not pick the Target integer range or storage/comparison implementation.

title: Ordered multi-operand integer min/max

level: MUST

## CST_048

`IntegerSum(iterable, start=None)` retains an integer iterable Value and an optional integer start Value as an immutable integer operation. The iterable must be a strictly typed `list[int]`, fixed-length Tuple with *all* int elements, or integer `Range`; typed empty List and empty Tuple are permitted. The default start is integer zero. Evaluate the iterable expression once, then an explicit start expression once, then add elements in order. Neither Model nor Frontend computes/folds the sum. Arbitrary Iterables, string concatenation, bool promotion, custom addition and Target integer ranges are excluded; Realization handles representation and range restrictions.

title: Typed integer sum and evaluation order

level: MUST

## CST_049

`BooleanAggregate(operation, iterable)` is an immutable Boolean Value for `any`/`all` over `list[bool]` or fixed Tuple with exclusively Boolean elements. Evaluate the iterable expression once and each needed element in order. `any` stops at the first true and returns false for empty input; `all` stops at the first false and returns true for empty input. Do not accept arbitrary Python truthiness, Iterables, special methods or non-Boolean elements. Short-circuit execution is a Realization obligation, not a Model action.

title: Ordered short-circuit any/all on typed Booleans

level: MUST

## CST_050

`ValueKind.FLOAT` and `FloatingLiteral(value: float)` represent an immutable float constant distinct from int/string `Literal`. Accept only a *finite* exact Python float, rejecting bool, int and nonfinite values. Propagate float types through typed Symbols, functions and existing container shapes. Do not automatically select a memory Interface or Target representation based on the type.

title: Explicit floating-point Values distinct from integers

level: MUST

## CST_051

`FloatingArithmetic(left, operator, right)` supports `+`, `-`, `*`, `/` for strictly FLOAT operands; `FloatingUnary(operator, operand)` supports unary `+` and `-`. Preserve operand expressions, operators and evaluation order without Frontend precomputation. Realization must reproduce Python float behavior, including rounding and division-by-zero outcomes, or reject. Do not silently include integer division or mixed int/float operations in the old Arithmetic Construct.

title: Typed floating-point arithmetic distinct from integer arithmetic

level: MUST

## CST_052

`FloatingComparison` stores `<`, `<=`, `>`, `>=`, `==`, or `!=` between strictly float operands and yields Boolean. Evaluate operands once each from left to right, preserving comparisons when NaN arises from expressions. Do not add implicit int/bool conversion, chained comparisons here, or Target float ABI assumptions.

title: Floating-point comparison and type boundaries

level: MUST

## CST_053

`StringConcat(left, right)` concatenates two Unicode Strings; `StringRepeat(left, right)` repeats str by int for either `str * int` or `int * str`. Both preserve unexecuted child Values and evaluate them exactly once in source order. Repetition by a negative count yields the empty string, as in Python. The existing integer Arithmetic domain remains unchanged.

title: String concatenation and integer-count repetition

level: MUST

## CST_054

`StringComparison` records six ordering/equality relations on str pairs, using lexicographic order of Unicode code-point sequences. `StringContains(needle, haystack, negate)` records substring membership or its negation with Boolean result. Evaluate child expressions once each in source order; do not implicitly use arbitrary Python object special methods or comparisons with non-Strings.

title: Static string comparisons and substring containment

level: MUST

## CST_055

`StringElement(source, index)` is a String Value indexing a Unicode code-point sequence with an integer index. Negative indices count from the end; out-of-range indices raise runtime `IndexError`. Neither Frontend nor Model evaluates the index early. Slices, assignment, byte indexing and arbitrary `__getitem__` are out of scope. Correct Unicode representation and exception behavior belong to Realization.

title: Typed single-element String indexing

level: MUST

## CST_056

For `FunctionCall`, `MethodCall` and `InstanceCreation`, the `arguments` tuple retains the normalized values in *declared parameter order* after arity/type validation. A separate `evaluation_order` gives the permutation of parameter indices that describes source-expression evaluation order, defaulting to `(0, 1, ...)`. Read-only derived `argument_evaluation_order` and `evaluation_arguments` expose the actual evaluation sequence. Reject missing, duplicated or invalid indices during construction. Binding order and evaluation order are different contracts: Realization must enforce once-only evaluation and the original order even if Target argument evaluation order is unspecified. Preserve the existing declared-order `arg0` etc. Slots and direct-call type rules; do not infer keyword parameter names on indirect function-value calls.

title: Separating keyword-argument binding from evaluation order

level: MUST

## CST_057

`FunctionSignature.parameter_defaults` is an immutable aligned sequence of `Value | None`, one per parameter. `None` denotes *absence of a default*; Python's literal None is `NoneLiteral()`. Defaults must be compatible literals of int, finite float, str, bool or None only; invalid placements before required parameters/receivers, mutable objects and arbitrary expressions are rejected. A `Parameter` in `FunctionDefinition.parts()` exposes a `default` child only when one exists. Call `arguments` Slots include omitted defaults inserted in declared order, while `omitted_arguments` records omitted parameter positions and `supplied_evaluation_arguments` exposes *only source-supplied* expressions in written order. Virtually dispatched overrides must agree with base methods on omitted positions and default values. Filled defaults are immutable literals; no general Python definition-time evaluation or shared mutable-default semantics is promised. The Model does not perform Target realization.

title: Static scalar defaults and omitted arguments

level: MUST

## CST_058

`MethodKind.STATIC` represents a class-owned function with no receiver, using existing FunctionDefinition, FunctionSignature and Parameter nodes. `ClassMethodCall` records a class-sourced `ClassReference` and arguments. Validate typed arguments, restricted static defaults and explicit argument evaluation order. Do not treat this as an instance receiver or synthesize a runtime Python descriptor object.

title: Static methods with explicit class ownership

level: MUST

## CST_059

`MethodKind.CLASS` has a first parameter of `ParameterRole.CLASS_RECEIVER`, distinct from an instance RECEIVER and independent of the spelling `cls`. `ClassMethodCall.class_source` retains either a statically named class `ClassReference` or a typed Reference to a class receiver. Calling through a derived class must carry the *runtime derived class identity*. `ClassReceiverCreation` instantiates that same runtime class, not the class where the method was originally declared. Call and creation preserve keyword binding, expression evaluation order and omitted arguments; unsupported Realizations reject them.

title: Class methods and preservation of runtime class receivers

level: MUST

## CST_060

Restricted `@dataclass` is a normalization rule, not a general decorator Construct: from static field declarations it produces existing `ClassSignature`, `FieldDefinition`, and synthesized `FunctionSignature(__init__)`, `FunctionDefinition`, and `FieldInitialize`. Preserve typed field declaration order, static scalar defaults and instantiation with omitted or keyword-specified arguments under existing contracts. Do *not* claim automatically generated `__repr__`, `__eq__`, `__hash__`, `__post_init__`, `default_factory`, frozen, slots, arbitrary inheritance or general class rewriting from Python dataclasses.

title: Normalizing restricted dataclasses into existing Constructs

level: MUST

## CST_061

A typed lambda is a `LambdaValue` *expression* containing existing FunctionDefinition/FunctionSignature/Parameter/Block/Return Constructs rather than a separate closure or declaration family. It retains typed parameters, exactly one return expression, lexical binding relationships and the expression's evaluation location. When evaluated, the resulting function value must reference the appropriate outer lexical environment for each call; Realization controls environment allocation, sharing and lifetime. `LambdaValue.parts()` exposes a `definition` child, and `lexical_captures(definition)` can derive static captures. Do not infer arbitrary dynamic Python function-object behavior. Existing FunctionCall, FunctionValueCall and FunctionDefinition meanings remain unchanged.

title: Typed anonymous functions as expressions and lexical environments

level: MUST

## CST_062

`Pass` is an explicit statement with no runtime effects; `parts()` is empty and the Model prescribes no Target syntax. `docstring: str | None` on Program/FunctionDefinition/ClassDefinition retains the original first-position string literal as static declaration documentation, distinguishing an empty docstring from absence. It is not an executed child Construct or output Slot. This does not introduce Python's general `__doc__` attribute, introspection or arbitrary runtime string-expression behavior. Other type/call/class contracts remain unchanged; Realization is not required to emit the docstring unless Target-specific output demands it.

title: No-op statements and static declaration docstrings

level: MUST

## CST_063

`AugAssign(target, operator, value, mode)` retains typed augmented assignment without desugaring into a read, binary operation and Assign. Initially, `target` is restricted to Reference or FieldRead, with strict int/int `+`, `-`, `*`, `//`, `%` and float/float `+`, `-`, `*`, `/` (plus later CST_065 bitwise additions). `AugAssignMode.REBIND` reads a scalar, computes a new value, and rebinds that same destination; destructive `IN_PLACE` mutation is not accepted. Determine the storage destination (including field receiver) and read its current value *once*, then evaluate the RHS *once*. Arithmetic follows existing Arithmetic/FloatingArithmetic semantics. Target temporaries and field-update syntax are not fixed by the Model; required evaluation/rebinding obligations are registered by the Construct provider as AdmissionRules.

title: Typed scalar augmented assignment and single destination evaluation

level: MUST

## CST_064

`ComparisonChain(operands, operators)` retains at least three ordered Values and the comparisons between adjacent Values, with Boolean result. Operators are exactly `<`, `<=`, `>`, `>=`, `==`, `!=`; all operands must have the same explicit type, restricted to int, float or str. Evaluate only needed expressions, once each from left to right, reusing each intermediate operand instead of reevaluating it. Stop immediately at a false comparison, without evaluating later operands. Naively duplicating Comparison nodes or unconditionally splitting into BooleanOperation would break this contract and is prohibited in Frontend/Model. Realization must ensure order, single evaluation and short-circuit or reject; the Model does not decide Target temporaries or operand execution order.

title: Typed comparison chains and once-only intermediate values

level: MUST

## CST_065

`IntegerTrueDivision(left, right)` independently retains two strictly integer operands in order but returns FLOAT. It is not implicitly translated to integer floor division or FloatingArithmetic. Python's mathematical true-division behavior includes division-by-zero and potential errors when converting very large ints to float; neither Frontend nor Model computes it. `Arithmetic` adds strict integer `&`, `|`, `^`, `<<`, `>>`, `IntegerUnary` adds `~`, and `AugAssign` accepts corresponding integer bitwise operations while preserving its single-evaluation/rebinding rules. Python's arbitrary-precision, infinitely sign-extended bitwise semantics for negative ints apply; a negative shift count is a runtime error, not a construction-time evaluation. Retain once-only left-to-right operand evaluation. The Construct provider supplies new AdmissionRules for bitwise operations, shift counts, and true division. A supports declaration is not proof of preservation; Target integer width or arithmetic is not imposed on the Model.

title: Integer bit operations and true division of integers

level: MUST

## CST_066

`IntrinsicDefinition` is a Target-independent declaration of a typed primitive operation: it records an identifier, optional receiver `ValueType`, a fixed sequence of positional argument types, return `ValueType`, and additional concrete semantic-contract keys. `IntrinsicCall` retains the immutable resolved definition, optional receiver expression and ordered argument expressions, checking types and arity during normalization. If present, evaluate the receiver *once before* arguments, each argument once in source order. Providers define operation semantics, mutation and exception requirements; the Model neither executes the call nor picks a Target ABI or String encoding. `variant()` yields `intrinsic.<receiver kind or global>.<name>` and `parts()` exposes the existing `receiver` and `arg0`, etc. IntrinsicRegistry overloads and limited signature-local type variables follow CST_067. No runtime attribute lookup or implicit Target implementation selection is introduced. Construct-provided AdmissionRules derive the operation key plus receiver-once, receiver-before-args, per-arg-once and multi-arg ordering obligations. Declared support is not a semantic-preservation proof.

title: Provider-defined typed primitives and IntrinsicCall

level: MUST

## CST_067

`IntrinsicDefinition.key` identifies an operation *family*, such as `intrinsic.global.str` or `intrinsic.list.append`, rather than separate keys per parameter type. IntrinsicRegistry may register several definitions under one key when receiver/positional static signatures differ, but rejects duplicate identical signatures and attempts to replace them with different returns or contracts. Resolution uses only known static types and argument count; no match or ambiguous multiple matches fail. No implicit conversion, overload priority, dynamic dispatch or runtime-result inference. `IntrinsicTypeVar` and `IntrinsicListType` are signature-local *patterns* used to bind relationships such as `list[T].append(T)` from the known receiver element type and argument type. An unbound type variable in the return type is rejected at registration. IntrinsicCall retains the concrete resolved definition, never runtime type variables or general type inference. Obligations are signature-specific even for a shared key: Realization must support both the family key and the selected signature's semantics or reject; its declaration does not establish proof.

title: Overloaded static primitive signatures and local type variables

level: MUST

## CST_068

The standard provider `standard_intrinsics()` declares zero-argument `str()`, `int()`, and `float()`, plus one-argument conversions from exact int/float/str/bool, and `str.upper()` / `str.lower()`, each with fixed static signatures and signature-specific obligations. Runtime behavior includes decimal integer spellings; float-to-str rules for `1.0`, `-0.0` and nonfinite results; Boolean `True`/`False`; string-to-number syntax and errors; float-to-int truncation toward zero and errors on nonfinite values; range overflow converting arbitrary-precision int to float; and Unicode case conversion, which may change length. Zero-argument results are `""`, `0`, and `0.0`, respectively. Do not constant-fold by input runtime values or implicitly promote types. Exclude `str(list)`, `int(str, base)`, arbitrary dynamic `__str__`/`__int__`/`__float__`, general object conversion and formatting. Realization must honor both the family key and signature-specific contract; the Model prescribes no Target output algorithm.

title: Typed standard conversions and Unicode string operations

level: MUST

## CST_069

`FormattedString(fragments)` retains at least one string-typed Value and concatenates fragment results as Unicode Strings after evaluating each once left to right. In f-strings, Frontend uses a typed `str(x)` IntrinsicCall for embedded expressions (FRT_066), reusing CST_068's type-specific string conversion contracts. No format specs, `!r`/`!a`, or arbitrary user `__format__` are supported. The Model chooses no Target concatenation technique. `PrintValues(values)` retains zero or more string Values; all arguments must be evaluated *once in source order before output starts*, then printed to standard output separated by spaces and ending in a newline. Value-to-string conversion is represented by distinct typed IntrinsicCalls, separate from print ordering obligations. Legacy `Call(print, (str,))` stays for existing standard Pack recipes. Realization must reject unsupported new Constructs.

title: Unformatted f-strings and multi-value output

level: MUST

## CST_071

`Membership(element, container, negate)` retains an ordered left Value and right typed `list[T]` or `dict[K,V]` and returns Boolean. Evaluate the left once before the right once, then test membership and negate only if requested. List membership searches from the start using identity or Python equality. Dict membership uses key hashing/equality, never value membership. Require the element's known ValueType to be assignable to the List element type or Dict key type. If the RHS is String, use the existing `StringContains` Unicode-substring contract and its separate Admission requirement. Other types and arbitrary Python `__contains__` are excluded. The Model does not execute lookup or choose Target storage/hash schemes; typed `membership.*` semantics must be declared through Admission.

title: Typed List and Dict membership semantics

level: MUST

## CST_070

`UnpackAssign(targets, value)` holds a fixed-length sequence of already declared, ordinarily typed Reference destinations and a typed Tuple Value of the same length. Validate per-position assignability at construction; reject mismatched length/type and attempts to rebind mapped objects or receiver references. At runtime evaluate the entire RHS *once*, establish all positional values, then assign destinations in left-to-right order. Duplicate destinations are legal and the final assignment wins. Do not desugar `a, b = b, a` into unrelated Assigns or dictate Target temporaries. Realization must reject if unable to preserve RHS capture and assignment order.

title: Fixed-length Tuple unpack assignment

level: MUST

## CST_072

`SliceValue(source, start, stop, step)` retains a known typed List or String source and distinguishes supplied boundary expressions from omitted `None` for each component. Evaluate source first, then present `start`, `stop`, `step` once each in that order. Python runtime slicing semantics cover negative indices, clamping out-of-range indices, negative steps and their interactions with omitted boundaries; a runtime step of zero raises `ValueError`, not a Model-construction error from evaluating an expression. A List yields a new *outer* List of the same element type, whereas a String yields selected Unicode code points as String. List elements may still alias original objects: no deep copy is promised. Tuple/Dict/arbitrary `__getitem__` slicing is excluded. Realization must explicitly support evaluation order, Python index normalization, shallow-copy or Unicode semantics. Target indexing and memory layout remain unspecified.

title: Omitted bounds and shallow copies in typed slices

level: MUST

## CST_073

`IterationEntry(target, iterable, introduces_binding)` retains one Reference to a typed Symbol updated by the loop and the iterable Value. `False` means updating an existing typed binding; `True` means introducing the binding at the iteration entry. Both update the *same Symbol* on every iteration rather than allocating a new Symbol per iteration. With an empty iterable an introduced variable may never become bound, so the Model inserts no fictional initial value or Initialize node. The flag does not prescribe Target variable-declaration placement; `parts()` still exposes only `target` and `iterable`. Introduced bindings additionally require the provider's `iteration.binding.introduced` Admission support, alongside existing iteration, break/continue and normal-completion else obligations. Old typed iteration entries keep the default `False` behavior.

title: Existing versus introduced iteration bindings

level: MUST

## CST_076

`ValueType.label` may hold a `KindLabel(name, arguments)` representing a word of `pyinto.kinds`. `name` is the word and `arguments` is a sequence of positive integers or `ValueType` values, recorded exactly as written in the source. The Host neither defines nor checks what a label means (size, range, representation, or run-time behavior). Labels do not take part in `ValueType` equality or hashing; type compatibility is decided only by the Python-side kind and structure. The single additional rule is that a `None`-typed value labeled `Void` / `Nil` / `Null` may be assigned or bound to a declared type that carries a label. `annotation()` returns the label's spelling when present (e.g. `Pointer[Int[32]]`).

title: Carrying uninterpreted kind labels

level: MUST

## CST_077

Kind words for values, comparisons, and pointer operations are recorded in the Model by these Constructs. `NoneAlias(name)` is a `Void` / `Nil` / `Null` value whose variant is `void` / `nil` / `null` respectively. `NoneAliasComparison(left, operator, right)` is a `==` / `!=` comparison in which one side is a None alias and the other is a labeled value. `AddressOf(target)` makes a value labeled `Pointer[type of the variable]` from a `Reference` to a typed variable; `PointerLoad(pointer)` makes a `T` value from a value labeled `Pointer[T]`; and `PointerStore(pointer, value)` is a statement writing a value assignable to `T` through a `Pointer[T]`. These carry no execution meaning and no Admission semantic obligations; the Target decides how to realize them.

title: Constructs for kind values, comparisons, and pointer operations

level: MUST

## CST_078

`ClassDefinition.labels` holds the `@Interface` / `@MixIn` / `@Implements(...)` attached to a class as `KindLabel` values in source order. The arguments of `Implements` are `ValueType` values carrying the `InstanceType` of each implemented class. Duplicate words are rejected. Labels do not change inheritance, the method set, or whether the class can be instantiated; they are information passed to Targets only.

title: Recording kind words attached to classes

level: MUST

## CST_079

The dynamic-memory vocabulary expresses shape and ownership as type labels. `Buffer[T]` is a sequence of `T` whose length is decided at run time and has the Python-side shape `list[T]`. `Owned[X]` and `Shared[X]` keep the Python-side shape of `X` and add an ownership label; `X` may be either a single type or `Buffer[T]`. An unlabeled `Buffer[T]` denotes a non-owning sequence. The Host defines no meaning for these (how storage is obtained, lifetimes, or the sharing mechanism).

title: Shape and ownership labels for dynamic memory

level: MUST

## CST_080

Dynamic-memory operations are recorded as these Constructs. `MemoryNew(element_type, value)` makes an `Owned[T]` value and `MemoryNewBuffer(element_type, length, value)` an `Owned[Buffer[T]]` value. `MemoryRelease(handle)` is a statement marking the end of an `Owned` / `Shared` value's lifetime; `MemoryResize(target, length)` is a statement changing the length of an owned `Buffer` variable; `MemoryLength(handle)` is the length of a `Buffer`; `MemoryBorrow(handle)` is a non-owning view that is a `Pointer[T]` for a single value and an unlabeled `Buffer[T]` for a sequence; and `MemoryCopy(destination, source)` and `MemoryFill(handle, value)` are statements copying between `Buffer` values and setting every element. `MemoryRelease` and `MemoryBorrow` have a `single` / `buffer` variant derived from the handle's type. None of these carries execution meaning or Admission semantic obligations; the Target decides how to realize them from the type labels.

title: Constructs for dynamic-memory operations

level: MUST

## CST_081

`Wide[X]` / `Narrow[X]` in `pyinto.kinds.datatypes.general` express size relative to `int` / `float`, with nesting depth giving the number of steps. `Unsigned[X]` expresses an integer without sign and is always written outermost. `Size` / `Index` / `Byte` express integer roles. All of them keep the Python-side shape of the base type, and the Host defines no actual size or representation. So that each meaning has one spelling, mixing `Wide` and `Narrow`, writing `Unsigned` inside, applying `Unsigned` to non-integers, and applying `Wide` / `Narrow` to anything other than a base type are rejected.

title: General datatypes: relative size, sign, and roles

level: MUST
