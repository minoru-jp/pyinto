# Construct / Variant Reference

This table is generated from `variant_domain()` for Construct classes exported by `pyinto.interfaces.language`. It is a guard against inventing variant names. It does **not** enumerate every external provider or extension under `pyinto.constructs`.

- A finite `frozenset` is strictly checked when Realizations are registered.
- `None` is an open domain that cannot be exhaustively enumerated at registration time; `"*"` can match it.
- `variant = "*"` selects any variant, including future additions.
- Omitting `variant` means **only** `"default"`; registration fails if the type has no such variant.
- Some direct builtin Calls use a separate named registration route rather than the Construct variant mechanism.

**Important:** Listing a Construct does not imply the Frontend can produce it for arbitrary Python syntax, that a given Target can realize it, or that its semantics are preserved. Consult [Specification](../specification/INDEX.md) for `parts()` contracts.

## Public Construct variant domains

Aliases are listed under each **publicly exported name**. After changing Construct variants, regenerate the Japanese table with `python scripts/docs.py render` and update this published derivative.

| Construct | variant_domain() | Notes |
| --- | --- | --- |
| AddressOf | `default` |  |
| Arithmetic | `default` |  |
| Assign | `default` |  |
| AugAssign | `default` |  |
| Block | `default` |  |
| BooleanLiteral | `false`, `true` |  |
| BooleanNot | `default` |  |
| BooleanOperation | `default` |  |
| Branch | `default`, `with_else` |  |
| Break | `default` |  |
| Call | `default` |  |
| ClassDefinition | `default` |  |
| ClassMethodCall | `default` |  |
| ClassReceiverCreation | `default` |  |
| ClassReference | `default` |  |
| Comparison | `default` |  |
| ComparisonChain | `default` |  |
| ConditionalExpression | `default` |  |
| ContextEntry | `default`, `with_target` |  |
| Continue | `default` |  |
| DictElement | `default` |  |
| DictElementAssign | `default` |  |
| DictEntry | `default` |  |
| DictValue | `default` |  |
| ExceptHandler | `default` |  |
| ExpressionStatement | `default` |  |
| FieldDefinition | `default` |  |
| FieldInitialize | `default` |  |
| FieldRead | `default` |  |
| FieldWrite | `default` |  |
| FloatingArithmetic | `default` |  |
| FloatingComparison | `default` |  |
| FloatingLiteral | `default` |  |
| FloatingUnary | `default` |  |
| For | `default`, `with_else` |  |
| FormattedString | `default` |  |
| FunctionCall | `default` |  |
| FunctionDefinition | `default` |  |
| FunctionValueCall | `default` |  |
| Initialize | `default` |  |
| InstanceCreation | `default` |  |
| IntegerTrueDivision | `default` |  |
| IntegerUnary | `default` |  |
| IntrinsicCall | open domain (`None`) | `variant = "*"` matches every variant |
| IterationEntry | `default` |  |
| LambdaValue | `default` |  |
| ListElement | `default` |  |
| ListElementAssign | `default` |  |
| ListValue | `default` |  |
| Literal | `integer`, `string` |  |
| Membership | `dict_in`, `dict_not_in`, `list_in`, `list_not_in` |  |
| MemoryBorrow | `buffer`, `single` |  |
| MemoryCopy | `default` |  |
| MemoryFill | `default` |  |
| MemoryLength | `default` |  |
| MemoryNew | `default` |  |
| MemoryNewBuffer | `default` |  |
| MemoryRelease | `buffer`, `single` |  |
| MemoryResize | `default` |  |
| MethodCall | `default` |  |
| NoneAlias | `nil`, `null`, `void` |  |
| NoneAliasComparison | `default` |  |
| NoneLiteral | `default` |  |
| Parameter | `default` |  |
| Pass | `default` |  |
| PointerLoad | `default` |  |
| PointerStore | `default` |  |
| Program | `default` |  |
| Raise | `default`, `with_message` |  |
| Reference | `default` |  |
| Return | `default`, `with_value` |  |
| SliceValue | `list`, `string` |  |
| StringComparison | `default` |  |
| StringConcat | `default` |  |
| StringContains | `in`, `not_in` |  |
| StringElement | `default` |  |
| StringRepeat | `default` |  |
| Try | `finally`, `handlers`, `handlers_finally` |  |
| TupleElement | `default` |  |
| TupleValue | `default` |  |
| UnpackAssign | `default` |  |
| Value | `default` |  |
| While | `default`, `with_else` |  |
| With | `default` |  |
