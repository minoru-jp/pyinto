<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/realizer/construct_reference.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# Construct / Variant Reference

以下の表は`pyinto.interfaces.language`に公開されているConstructクラスから
`variant_domain()`を参照して生成する。Realizerの実装者が存在しないvariantを推測しないための台帳。
`pyinto.constructs`のその他の外部拡張型・任意の外部提供者まで網羅するものではない。

- `frozenset`：登録時にvariant名を厳密検証する。
- `None`：候補を構築時に列挙できない開いた定義域。`"*"`で包括的に扱える。
- `variant = "*"`：今後追加されるvariantを含む全てに一致。
- `variant`省略：`"default"`だけを指定（`default`が存在しない型は拒否）。
- `Call`：直接builtin Callは一部、Constructクラスのvariantとは別の名前登録経路を使用。

**注意**：表に掲載したことはFrontendがどのPython構文でも生成できること、Targetが
それを実現できること、意味保存を保証することを意味しない。
個々のConstructの`parts()`と契約は[Specification](../specification/INDEX.md)を参照。

## 公開Constructのvariant一覧

同一クラスの別名公開が発生した場合も、**公開名**を表のキーとして保持する。
自動生成表なので、Constructのvariant追加後は`python scripts/docs.py render`で更新する。

public Construct variants:

| Construct | variant_domain() | 備考 |
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
| IntrinsicCall | 開いた定義域 (`None`) | `variant = "*"` で全variantに一致 |
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
