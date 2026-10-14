"""English contract synopses pending complete human/LLM-reviewed clause translation.

This is translation support, NOT a second normative source. Do not infer contract
behavior from the abridged English text without checking the Japanese canon.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "devdocs/canonical_documents/specification"
OUTPUT = ROOT / "docs/specification"

CONSTRUCT: dict[str, str] = {
    "CST_001": "Constructs represent normalized operations and named children, not Python AST nodes. `parts()` exposes named parts and `variant()` selects structural variants; Constructs do not themselves emit code.",
    "CST_075": '`variant_domain()` returns a finite `frozenset[str]` of possible variants, or `None` for open domains. Built-in overrides declare `VARIANTS`; the default-only type has `{"default"}`. External overrides without `VARIANTS` are open. This Target-independent metadata supports declaration validation.',
    "CST_002": "Typed `Symbol` declarations retain full recursive `ValueType`, or `PortType` with source/variant/integer constraints. Builtin-only symbols have no type. `kind` and type details are derived rather than duplicated; Port objects must not be silently coerced to ordinary values.",
    "CST_003": "`Block` stores ordered children. `Branch` and `While` hold conditions, bodies, and optional else Blocks; an else selects `with_else`. `Break` and `Continue` are distinct Constructs.",
    "CST_004": "`For.parts()` exposes `IterationEntry`, body, and optional else only. `Range` preserves its 1–3 integer arguments, and `bounds()` supplies the standard defaults, start 0 and step 1. Target-specific loop Slots are not embedded in the Model.",
    "CST_005": "`With` retains one or more ordered `ContextEntry` objects and a body; entries include context expressions and optional targets. Representability in the Model does not imply the Target can implement correct exit behavior.",
    "CST_006": "No Construct offers `to_source()` or `to_c()`. Conversion entry points are `pyinto.convert()` and `pyinto.realize()`; Models do not depend on Target Packs or generators.",
    "CST_007": "`parts()` exposes Target-neutral `Identifier`, `Symbol`, and ordered tuples rather than output-only `Name`, `TypeName`, `Joined`, or `Requirements`. Output requirements are not Program Model fields.",
    "CST_008": "`With` exposes ordered entries under `entry0`, `entry1`, etc. The Realization, not the Model, decides punctuation, separators, and line breaks.",
    "CST_009": "`For.parts()` contains only `entry`, `body`, and optional `otherwise`, including non-Range iteration. The Realization chooses any Target-specific `target/start/stop/step` Slot expansion.",
    "CST_010": "`Program` exposes its existing `body` as a Model part, not output-only `requirements`; the latter is a Composition-owned Slot.",
    "CST_011": "`Literal` accepts exactly Python `int` or `str` (not `bool`, `float`, `None`, or arbitrary objects). Invalid values fail at construction; representation and Target integer range are Realization concerns.",
    "CST_012": "Frontend Construct Trees are reusable, Target-independent, and free of Python AST/Layout generation nodes. Applying different Realizations must not mutate the Model; this is a usage contract, not an enforced immutable proxy.",
    "CST_013": "`Construct.HOLES` lists potentially exposed Model names, not mandatory Template Slots. `parts()` lists only present parts; dynamically numbered names use `accepts_part_name()`. Missing parts fail at composition time.",
    "CST_014": "Construct constructors validate operator/type consistency, assignment types, and Boolean conditions, raising `ConstructError` before Realization. `parts()` is structural inspection, not Target-dependent validation.",
    "CST_015": "`Arithmetic` retains ordered integer operands and arithmetic/bitwise operators; `IntegerUnary` retains unary operators. Validate types and operators without constant folding or rewriting Python division/modulo into Target-specific forms.",
    "CST_016": "`BooleanOperation` preserves the ordered operands of `and`/`or` and their short-circuit semantics; `BooleanNot` keeps a Boolean operand. The Target must implement evaluation, not the Model.",
    "CST_017": "`FunctionSignature` records name, ordered typed parameters, and a recursive return type. `FunctionDefinition` records signature/body and checks explicit returns, including nested control bodies but excluding nested function/lambda returns. It does not prove all paths return or determine Target calling conventions.",
    "CST_018": "`Return` has an optional value; `FunctionCall` has a resolved signature, ordered arguments, and result type. Check argument types/count and return compatibility at Model construction. For `-> None`, only bare return or explicit `NoneLiteral` is valid; non-None returns require values. `Any`/`object` retain broader accepted values.",
    "CST_074": "Typed `*args: T` on top-level functions is one variadic `Symbol` with `TupleType(variadic_element_type=T)`, distinct from fixed tuples and lists. Calls bind fixed arguments and retain surplus static positional arguments individually in source order. Targets must form one immutable tuple at runtime and support `function.variadic.tuple_binding` / `call.variadic.tuple_binding`. No dynamic unpacking, variadic function values, or Target ABI assumptions.",
    "CST_019": "Nested functions reuse `FunctionDefinition` inside Blocks. Lexical declaration identity is retained by `FunctionSignature.scope`, `Symbol.scope`, and resolved call/reference links. No separate nested-function Construct or Target storage scheme is imposed.",
    "CST_020": "First-class function values use `ValueKind.FUNCTION` and recursive `CallableType`. Structural type shapes must match exactly, not by inferred Python Callable subtyping. Typed assignment, declaration, and direct argument compatibility are checked.",
    "CST_021": "A declaration retains `FunctionSignature`, with stable `value_symbol` identifying its callable value when the signature is complete. References and function-valued results keep callable type shape. Static declarations and runtime closure instances are distinct; unsupported Port-shaped signatures cannot silently be made into function values.",
    "CST_022": "`FunctionValueCall` stores a function-typed callee plus ordered positional arguments. It validates type shape/count and propagates the callable return type. Evaluate the callee once **before** arguments, then arguments in source order; Target storage/calling conventions are not prescribed.",
    "CST_023": "`lexical_captures(definition)` projects directly referenced outer-function Symbols in first-use order, preserving declaration identity. It excludes module scope, local/parameter names, and nested children’s own bodies. No new Closure Construct is needed.",
    "CST_024": "Symbols and signatures describe declarations, not runtime environments. Distinct factory calls must retain distinct closure environments, shared captured binding semantics, and appropriate lifetimes. These Target obligations are not proved by direct-only `lexical_captures` analysis.",
    "CST_025": "Fixed-length `TupleType` retains ordered immutable element shapes, even when nested in function signatures and other types. `TupleValue` retains ordered elements (including empty); mismatched shapes fail instead of inferring Python tuple covariance.",
    "CST_026": "`TupleElement` reads a statically known nonnegative in-range tuple index and exports `source` and `index`. Evaluate its source once; negative/dynamic indices and writable tuple indexing are not included.",
    "CST_027": "`Raise` records `ValueError`, `TypeError`, or `RuntimeError` plus an optional string message expression, distinguishing omission from presence. General Python exception objects, classes, and attributes are not modeled.",
    "CST_028": "`ExceptHandler` holds ordered unique exception type names and a body. `Try` has a body, ordered handlers, optional else and finally; at least a handler or finally is required, and else requires a handler. `variant()` distinguishes handler/finally combinations.",
    "CST_029": "Exception handlers match in declared order on exceptions from the try body. Else executes only after normal completion without exceptional/control transfer. Finally runs on all exits and can override earlier transfers, following Python semantics. Targets unable to preserve this must reject it.",
    "CST_030": "`ListType` holds a single recursive element type with variable runtime length. `ListValue` preserves ordered expressions and homogeneous type checking, including typed empty lists. Aliases share a mutable object; Target storage and identity are not predetermined.",
    "CST_031": "`ListElement` and `ListElementAssign` distinguish element access/update from variable rebinding, validate integer indices and element types, and require Python observable behavior for negative/out-of-range indices, evaluation order, and mutation through aliases.",
    "CST_032": "`DictType` retains key/value shapes (only strict int/str keys), with ordered `DictEntry` expressions. Empty dictionaries require explicit types. Evaluate key/value expressions once in order; equal later keys replace values without changing the original insertion position. Aliases share mutable dictionaries.",
    "CST_033": "`DictElement` and `DictElementAssign` represent typed access and insert/update. Missing keys raise `KeyError`; updating preserves key position and inserting appends. Targets must preserve expression evaluation order, lookup failure, insertion order, and alias-visible mutations.",
    "CST_034": "`InstanceType(name, scope)` uses nominal identity; recursive type shapes preserve it. `ClassSignature` stores ordered fields/methods and requires typed `__init__`. `ClassDefinition` reuses `FunctionDefinition` method bodies. Dynamic Python metaclass behavior is excluded.",
    "CST_035": "Instance method receivers have `ParameterRole.RECEIVER` and a nominal instance type. The signature explicitly records the receiver; its name need not be `self`. Target representation as parameter/object/pointer is unconstrained.",
    "CST_036": "`InstanceCreation` allocates a fresh instance and calls declared `__init__`; assignment shares references. Fields and method calls preserve owners, typed arguments, single receiver evaluation, and left-to-right argument evaluation. ABI, memory lifetime, and storage are Target responsibilities.",
    "CST_037": "Static single inheritance is represented through nominal base references. Subtyping follows explicit ancestry and allows derived-to-base value assignment, not arbitrary variance in tuple/list/dict/callable shapes. Inherited members are resolved without copying declarations.",
    "CST_038": "`MethodCall` distinguishes runtime `VIRTUAL` dispatch from lexically anchored `SUPER` lookup. Virtual calls choose the closest override for the runtime class; super starts above the current defining class and retains the same receiver instance. Realization chooses tables/Slots/ABI.",
    "CST_039": "Derived classes declare their own fields and methods, with checks for inherited name conflicts and exactly matching override parameter/return shapes (except `__init__`). Field owners, receiver subtyping, and runtime virtual dispatch remain explicit obligations.",
    "CST_040": "Nominal type identity and alias relationships survive passing inherited instances through references, functions, collections, and captures. A base-typed reference can hold a derived instance without forcing virtual dispatch to the static class.",
    "CST_041": "Function-valued fields can be accessed through `FieldRead` and called using `FunctionValueCall`, without implicit method receiver binding. Inherited field owner identity and callee-before-argument evaluation are preserved.",
    "CST_042": "`BooleanLiteral` stores strict Python bool separately from int, returns variant `true` or `false`, and delegates Target spelling to Realization.",
    "CST_043": "`NoneLiteral()` is an explicit `ValueKind.NONE`, distinct from omitted optional fields such as `Return.value is None`. It is accepted only in existing compatible object/Any contexts, not as a general Optional/Union type.",
    "CST_044": "`ConditionalExpression` records typed condition/true/false branches and validates result-type compatibility. Evaluate the condition once and only the chosen branch; do not infer Union results or pre-evaluate the other branch.",
    "CST_045": "`Length` accepts strictly typed string, fixed tuple, list, and dictionary values and evaluates its operand once. Strings count Unicode code points, dictionaries count distinct keys, and mutable containers reflect runtime length. Do not infer `__len__` from arbitrary objects.",
    "CST_046": "`Absolute` supports signed integers only, evaluating once and demanding mathematical absolute value. Float, complex, custom `__abs__`, and bool-as-int are excluded.",
    "CST_047": "`Extremum` models min/max over two or more typed int arguments, evaluated once each in order. Iterable-only calls, key/default parameters, and arbitrary comparison protocols are excluded.",
    "CST_048": "`IntegerSum` aggregates a typed integer list, fixed int tuple, or integer Range with optional typed start (default zero). Evaluate the iterable before explicit start, then add elements in order. Do not constant-fold or generalize to arbitrary iterables.",
    "CST_049": "`BooleanAggregate` models any/all over typed Boolean lists or tuples, with left-to-right short-circuiting. Empty any is false; empty all is true. Python truthiness and arbitrary iterable protocols are excluded.",
    "CST_050": "`FloatingLiteral` and `ValueKind.FLOAT` represent finite Python float values independently of integer/string Literal. Reject int/bool/nonfinite literals and preserve types through composite shapes.",
    "CST_051": "`FloatingArithmetic` and `FloatingUnary` accept strict float operands and defined arithmetic/unary operators. Preserve Python float semantics, including rounding and exceptions; do not implicitly mix int and float.",
    "CST_052": "`FloatingComparison` performs typed float comparisons as Boolean results, evaluating operands in order and respecting IEEE/Python NaN behavior without implicit coercion.",
    "CST_053": "`StringConcat` and `StringRepeat` preserve source-ordered Unicode string concatenation and integer repetition. Negative counts yield empty strings; do not repurpose integer Arithmetic.",
    "CST_054": "`StringComparison` uses Unicode lexicographic ordering/equality; `StringContains` performs substring membership with optional negation. Both require strict strings and ordered, once-only operand evaluation.",
    "CST_055": "`StringElement` indexes Unicode code points with a typed integer; negative indices count from the end and out-of-range access raises IndexError. Slicing, assignment, bytes, and arbitrary `__getitem__` are excluded.",
    "CST_056": "Bound arguments remain in declaration order while `evaluation_order` separately records source evaluation order. Explicit argument evaluation, omission, and `argN` Slots are distinct; Targets must preserve once-only evaluation even when their language has unspecified argument order.",
    "CST_057": "Static parameter defaults are aligned immutable, typed literal Values or absent (`None`); `NoneLiteral()` means an actual None default. Bound Calls include omitted defaults in formal order while separately recording omitted positions and explicitly evaluated arguments. Overrides must match defaults/omissions.",
    "CST_058": "`MethodKind.STATIC` identifies a class-owned receiver-free function. `ClassMethodCall` records a `ClassReference` and typed explicit arguments, but does not synthesize Python descriptor objects.",
    "CST_059": "`MethodKind.CLASS` uses an explicit `CLASS_RECEIVER` parameter and passes the runtime class identity through inherited calls. `ClassReceiverCreation` creates the runtime receiver class, not always the declaration owner.",
    "CST_060": "A limited `@dataclass` is normalized to existing class, field, initializer, and field-initialization Constructs with typed ordered fields and static scalar defaults. General dataclass-generated methods and features such as `default_factory`, frozen, slots, and `__post_init__` are excluded.",
    "CST_061": "`LambdaValue` embeds an existing typed function definition/signature/body as an expression-valued function. It preserves the lexical capture relationship and creation site; runtime environment allocation and lifetime are Target obligations.",
    "CST_062": "`Pass` is a no-effect statement. Program/function/class declarations retain optional leading static docstrings, distinguishing empty from absent. Docstrings are not executable children or guaranteed output Slots.",
    "CST_063": "`AugAssign` preserves typed scalar rebinding without lowering to Assign+Arithmetic. Limited integer/float operators and Reference/FieldRead targets are accepted. Evaluate/read the target exactly once before the RHS, then rebind; in-place mutation is not implied.",
    "CST_064": "`ComparisonChain` retains three or more ordered same-typed int/float/str operands. Evaluate each needed expression once in order, reuse shared middle values, and short-circuit after a false comparison; do not blindly lower to independent comparisons.",
    "CST_065": "`IntegerTrueDivision` yields float from integer operands with Python exceptions. Integer bitwise and shift operators preserve unbounded signed semantics; negative shift counts fail at runtime. Operands are evaluated once in order; Target integer widths are not imposed by the Model.",
    "CST_066": "`IntrinsicDefinition` declares typed provider operations, receiver/arguments/return type, and semantic obligations. `IntrinsicCall` preserves resolved definitions and once-only ordered receiver/argument evaluation; its variant is a provider key, not dynamic attribute dispatch.",
    "CST_067": "`IntrinsicRegistry` allows distinct static signatures for one operation key, but rejects duplicates, ambiguous/no matches, or unbound return type variables. Signature-local type variables constrain known receiver/argument shapes and are resolved before constructing `IntrinsicCall`.",
    "CST_068": "`standard_intrinsics()` defines typed zero/one-argument str/int/float conversions and Unicode upper/lower methods with signature-specific Python semantics and exceptions. Unsupported dynamic protocols, `str(list)`, arbitrary formatting, and `int(str, base)` are excluded.",
    "CST_069": "`FormattedString` concatenates ordered typed string fragments once each; f-string expressions use typed `str(x)` intrinsics, not arbitrary formatting. `PrintValues` evaluates all expressions before output and emits space-separated values plus newline.",
    "CST_071": "`Membership` checks typed list elements or dictionary keys, evaluating operands once left-to-right and optionally negating the result. List equality/identity and dictionary hash/equality are distinct contracts; strings use separate `StringContains` semantics.",
    "CST_070": "`UnpackAssign` assigns a fixed-length typed tuple to existing Reference targets: evaluate RHS once in full, then write destinations left-to-right. Repeated destinations are allowed. Do not lower to independent Assign operations that break swapping.",
    "CST_072": "`SliceValue` retains missing start/stop/step distinctly and supports typed list/string slicing, Python index normalization, reverse steps, runtime zero-step errors, and shallow outer list copies / Unicode code-point slices. Evaluate source and present boundaries once in order.",
    "CST_073": "`IterationEntry` distinguishes rebinding an existing loop variable from introducing a new typed binding. A new variable may stay unbound if iteration is empty, so no fake initialization is inserted. `iteration.binding.introduced` is separately required for Target support.",
}

# For the Frontend, entries state the scope and boundaries, not every Japanese
# example/rejection detail. They remain synopses until reviewed clause by clause.
FRONTEND: dict[str, str] = {
    "FRT_001": "The Frontend statically normalizes Python AST into typed Constructs without executing source code or silently resolving unknown dynamic behavior.",
    "FRT_002": "New bindings require explicit type information; the Frontend retains declared types and rejects invalid or incompatible assignments and unsupported inference.",
    "FRT_003": "Name binding and control-flow bodies follow explicit scope/typing restrictions. Iteration sources and targets must have compatible statically known element types.",
    "FRT_004": "Only an explicitly supported expression subset is normalized; unsupported Python AST operators or constructs are rejected.",
    "FRT_005": "Only explicitly registered external API Interface Mappings are resolved. Static qualified names, module paths, signatures, argument binding and types are checked; unknown/dynamic resolution is rejected.",
    "FRT_006": "Separate normalization requests do not leak scope, name, or parser state between one another.",
    "FRT_007": "Typed integer arithmetic expressions become ordered `Arithmetic`/`IntegerUnary` Constructs, not precomputed results.",
    "FRT_008": "Boolean operations and negation are normalized with original operand order and short-circuit meaning.",
    "FRT_009": "Typed function declarations normalize into signatures, parameters, bodies, returns, and local lexical scopes.",
    "FRT_010": "Direct function references and Calls are statically resolved through explicit declarations and type/arity checks, with unsupported dynamic Calls rejected.",
    "FRT_011": "Nested function declarations use hierarchical lexical name resolution and preserve recursive references as resolved Model identities.",
    "FRT_012": "Lexical scope normalization does not imply full Python dynamic-scope, closure-mutation, or late-binding features are supported.",
    "FRT_013": "Explicit Callable annotations enable typed function-value References with complete callable shapes.",
    "FRT_014": "Function values have a limited acceptance boundary; indirect Calls must satisfy their own rules rather than being conflated with direct Calls.",
    "FRT_015": "Indirect Calls through typed function values normalize to `FunctionValueCall`, preserving the callee and ordered typed arguments.",
    "FRT_016": "Unsupported indirect Call forms and Target-specific execution semantics remain explicit rejection/Realization responsibilities.",
    "FRT_017": "Capture relationships retain lexical declaration identities; the Frontend does not guess per-call runtime closure environments.",
    "FRT_018": "Fixed-length tuple expressions and explicit recursive tuple types are normalized without loss of element order or shape.",
    "FRT_019": "Tuple indexing is statically restricted to known valid positions, rejecting dynamic or unsupported indexing.",
    "FRT_020": "A restricted subset of raise/try/except/else/finally syntax is normalized statically.",
    "FRT_021": "Unsupported exception syntax and Target Realizations are rejected rather than assuming full Python exception support.",
    "FRT_022": "Typed homogeneous lists, element access, and element updates are normalized with strict type checking and alias-relevant semantics.",
    "FRT_023": "List normalization is limited to known typed shapes and operations; Target runtime storage and element semantics remain separate obligations.",
    "FRT_024": "Typed dictionaries support restricted literals, subscripting, and updates with explicit key/value type matching.",
    "FRT_025": "Unsupported dictionary key/value shapes, dynamic behavior, and missing Target Realizations are rejected.",
    "FRT_026": "Static class definitions, nominal typed instances, fields, methods and explicit method receivers are normalized.",
    "FRT_027": "Python dynamic class machinery, arbitrary decorators, reflective members, and unsupported object features are outside the accepted subset.",
    "FRT_028": "Model support for classes does not imply Target class generation; unsupported class Realizations must reject.",
    "FRT_029": "Static single inheritance requires resolvable known bases and enforces nominal ancestry, with unsupported multiple/dynamic inheritance rejected.",
    "FRT_030": "Parent initialization and `super` use statically resolved ownership and receiver semantics.",
    "FRT_031": "Virtual method calls follow the static nominal class hierarchy while preserving runtime receiver dispatch semantics.",
    "FRT_032": "Virtual method calls on typed instance values from compound expressions preserve the expression and receiver evaluation semantics.",
    "FRT_033": "Ordinary method Calls are distinguished from indirect function-value Calls stored in fields.",
    "FRT_034": "Compound values and classes obey separate type/identity boundaries; Target Realizations remain responsible for unsupported runtime behavior.",
    "FRT_035": "Boolean literals normalize to a dedicated typed Value, not to integer Literals.",
    "FRT_036": "The `None` expression is accepted in a limited typed context, distinct from absent optional syntax fields.",
    "FRT_037": "Conditional expressions require a Boolean condition and statically compatible result types, preserving nonchosen-branch non-evaluation.",
    "FRT_038": "Boolean/None/conditional-expression adoption is limited; unsupported types or Target Realizations must be rejected.",
    "FRT_039": "The builtin `len()` is normalized only for explicitly typed supported strings and collections.",
    "FRT_040": "Integer `abs`, `min`, and `max` are statically type-checked and normalized in supported forms.",
    "FRT_041": "The accepted builtin subset is narrow; unsupported Python builtin forms or missing Realizations are rejected.",
    "FRT_042": "Integer `sum()` is accepted only for supported typed iterables and optional typed integer start values.",
    "FRT_043": "`any`/`all` normalize only over supported Boolean typed list/tuple inputs.",
    "FRT_044": "Aggregate builtin normalization requires explicit known name resolution; Target realization is an independent support boundary.",
    "FRT_045": "Typed float values and expressions normalize independently of integer arithmetic.",
    "FRT_046": "Supported Unicode string operations require strict static string/operand type checks.",
    "FRT_047": "Unsupported string/float operations and Target realization boundaries remain explicit and narrow.",
    "FRT_048": "Keyword arguments are statically bound by formal parameter name while original source expression evaluation order is retained separately.",
    "FRT_049": "Unknown/duplicate/missing keywords, type mismatches, dynamic argument expansions, and unsupported reorderings are rejected.",
    "FRT_050": "Only restricted immutable scalar default arguments are accepted; arbitrary mutable or evaluated defaults are rejected.",
    "FRT_051": "Missing defaults are filled into formal-order arguments without inventing source evaluations; explicitly supplied expressions retain source-order semantics.",
    "FRT_052": "Supported `@staticmethod` forms are statically normalized to receiver-free class-owned method signatures.",
    "FRT_053": "Supported classmethod calls preserve runtime class receiver identity, including inherited dispatch.",
    "FRT_054": "Restricted dataclass declarations normalize typed fields and synthesized initialization to existing class Constructs.",
    "FRT_055": "Decorator support is selective and statically declared; unsupported decorators remain outside the accepted subset.",
    "FRT_056": "Lambdas are typed and normalized only in explicit Callable contexts, with compatible parameter/return shapes.",
    "FRT_057": "Lambda support is restricted; Targets remain responsible for executable function values and lexical environments.",
    "FRT_058": "Registered typed decorators have explicit identification and effect normalization boundaries; unknown decorators are not guessed.",
    "FRT_059": "`pass` and leading declaration docstrings are normalized without creating unintended executable Constructs.",
    "FRT_060": "Supported scalar augmented assignment is normalized with strict target/operand typing and once-only target evaluation.",
    "FRT_061": "Typed comparison chains are distinguished from ordinary binary comparisons and preserve short-circuit/intermediate reuse.",
    "FRT_062": "Integer true division and strict typed bitwise operators normalize separately from regular float/integer arithmetic.",
    "FRT_063": "Registered typed intrinsics are resolved and normalized only through known provider definitions/signatures.",
    "FRT_064": "Overloaded intrinsic signatures are chosen by unique static type matches, with signature-local type variables concretized.",
    "FRT_065": "Standard conversions and Unicode string methods normalize only for supported typed signatures with provider contracts.",
    "FRT_066": "Limited unformatted f-strings and typed `print` normalize while preserving evaluation and output order.",
    "FRT_068": "Typed list element and dict key membership normalize to `Membership`, with string membership treated separately.",
    "FRT_067": "Fixed tuple unpack assignment is accepted for existing typed names with compatible positions and simultaneous RHS evaluation.",
    "FRT_069": "Typed list/string slicing preserves omitted bounds, step expressions, and Python index semantics.",
    "FRT_070": "A `for` loop can introduce a single new typed variable only when a statically known element type is available and scope rules permit it.",
    "FRT_071": "Typed declarations in supported control-flow bodies are usable only within their proven body/nested scope, not after or in unrelated branches.",
    "FRT_073": "A top-level user function may declare restricted typed `*args` with static positional calls; dynamic expansion and unsupported nested/method forms are rejected.",
    "FRT_072": "An explicit `global` at a restricted function-body location may rebind previously typed module variables; unsupported names/placements and scope conflicts are rejected.",
}


def render_summary(kind: str, meanings: dict[str, str], out: str) -> None:
    s = (SOURCE / f"{kind}.md").read_text()
    ids = re.findall(r"^## ([A-Z]{3}_\d+)\s*$", s, re.MULTILINE)
    assert set(ids) == set(meanings), (
        set(ids) - set(meanings),
        set(meanings) - set(ids),
    )
    rows = [
        f"# {out}",
        "",
        "> **English contract synopsis (abridged).** Every Japanese canonical contract ID is represented here, but detailed acceptance/rejection conditions have not all been translated. Consult the [Japanese canonical document](../../devdocs/canonical_documents/specification/"
        + kind
        + ".md) for normative wording. Do not infer undocumented support from this synopsis.",
        "",
    ]
    for cid in ids:
        rows.extend([f"## {cid}", "", meanings[cid], ""])
    (OUTPUT / f"{kind}.md").write_text("\n".join(rows), encoding="utf-8")


if __name__ == "__main__":
    render_summary("construct", CONSTRUCT, "Construct Model")
    render_summary("frontend", FRONTEND, "Python Frontend")
