<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/target_implementation/admission_reference.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# Admission Contract Reference

Targetの`pack_semantics`は成果物の**主張する意味保証**を選択する。
変換先のファイル拡張子や、`pack_dispatch`から自動的には推測しない。
既存の規範契約は[Composition Specification](../specification/composition.md)にあり、
このReferenceはTarget作者が誤宣言しないための適用ガイドである。

## ADM_001

HostはRealizer選択やSession生成の前に`admission.check_tree(root)`を行う。
Modelの具体的なConstruct型が提供者のAdmissionへ登録されていなければ、
`pack_unhandled="traverse"`でも拒否する。
`realize(..., admission=...)`で拡張Admissionを渡すときは基準の
`LANGUAGE_ADMISSION`を削除・置換できない（`require_baseline`）。
`convert(..., interface_mappings=...)`ではMapping側のAdmissionが使われる場合がある。

title: Model受理とTarget受理は異なる

level: MUST

related: [CMP_018](../specification/composition.md#cmp_018)

## ADM_002

Preservation（省略時）では、対象Constructの
`admission.required_contracts(node)`から必要契約を取り出し、
選択したRealizationの`supports`集合との**差集合**が空でなければ
`ConstructError`で拒否する。構造上到達しても必要な意味を保存できないなら
宣言を捏造せずTarget側で拒否する。
`supports`は意図した保証の自己宣言であり、コード実行結果の検証が別途必要。

title: 意味保存の要求契約

level: MUST

related: [CMP_013](../specification/composition.md#cmp_013), [CMP_017](../specification/composition.md#cmp_017)

## ADM_003

Projectionでは実行意味を成果物へ再現する必要がないため、
個別Realizationへの`required_contracts - supports`の照合を**要求しない**。
この緩和は未登録Modelの使用や、成果物に含める情報の誤報を許容するものではない。
何を抽出したかを明示し、その情報の正しさをテストする。
**射影の正しさについて汎用の契約自動検証は現行未実装**。

title: 意味射影の適用範囲

level: MUST

## ADM_004

`pack_unhandled="error"`は一致するRealizationがなければ拒否する。
`"traverse"`を使えるのはStructural + Projectionのみ。
その場合、一致しないConstructのVisitorを実行せず、`parts()`配下のConstructへ進む。
同じ型の別variantでも、正当な個別指定をしている場合は通過する。
非対応の型・variantを全て実現したと主張してはいけない。

title: 未処理とAdmissionの二層の境界

level: MUST

## ADM_005

具体的な契約名をコードの類推だけで捏造しない。
対応するModelのAdmission Rule、`required_contracts(node)`、
関連Specification、動作テストを確認する。
Variant選択の網羅性は`Construct.variant_domain()`の登録検証と
`variant @= "*"`の明示宣言で扱うが、意味契約との一致を代替しない。

title: 契約名の確認とvariantの独立性

level: MUST

## CATALOG

以下の一覧は`LANGUAGE_ADMISSION.declarations`のRuleから生成する。
`contracts`にある`.*`は**提供者側で許す名前空間ファミリーの記述**であり、
Realizerの`supports`にワイルドカードを置いてよいという意味ではない。
要求される**具体的なキー**は各Constructインスタンスで
`LANGUAGE_ADMISSION.required_contracts(node)`を呼んで確かめる。
`contracts`に掲載されても、常に全キーが要求されるわけではない。

title: Admission Ruleと契約キーの台帳

admission rule catalog:

| Rule | 対象Construct | 宣言可能な契約キー/ファミリー |
| --- | --- | --- |
| augmented_rebinding | AugAssign | `assignment.augmented.read_before_rhs`, `assignment.augmented.rebind`, `assignment.augmented.target_once` |
| bound_arguments | FunctionCall, InstanceCreation, ClassMethodCall, ClassReceiverCreation, MethodCall | `call.arguments.bound`, `call.arguments.left_to_right`, `call.arguments.reordered`, `call.defaults.omitted` |
| class_receiver | ClassMethodCall, ClassReceiverCreation | `class_receiver.runtime_identity` |
| collection_membership | Membership | `membership.dict.key_hash_equality`, `membership.list.identity_or_equality`, `membership.negated`, `membership.operands.left_to_right` |
| fixed_tuple_unpack | UnpackAssign | `assignment.unpack.rhs_once_before_writes`, `assignment.unpack.targets_left_to_right` |
| for_control_flow | For | `loop.for.break_continue`, `loop.for.normal_completion_else` |
| for_iteration_binding | For | `iteration.binding.introduced` |
| formatted_string_order | FormattedString | `format.string.fragments_once_in_order` |
| integer_operator_semantics | Arithmetic, IntegerUnary, AugAssign | `integer.bitwise.unbounded`, `integer.shift.python_counts` |
| integer_true_division | IntegerTrueDivision | `integer.true_division.python_float` |
| intrinsic_call_semantics | IntrinsicCall | `call.arguments.left_to_right`, `intrinsic.*` |
| iteration_binding | IterationEntry | `iteration.binding.introduced` |
| iteration_source | For, IterationEntry | `iteration.source.*` |
| method_dispatch | MethodCall | `method.dispatch.super`, `method.dispatch.virtual`, `method.lookup.lexical_base` |
| ordered_comparison_chain | ComparisonChain | `comparison.chain.left_to_right`, `comparison.chain.operands_once`, `comparison.chain.short_circuit` |
| ordered_operands | Arithmetic, IntegerTrueDivision, Comparison, FloatingArithmetic, FloatingComparison, StringConcat, StringRepeat, StringComparison, StringContains, StringElement | `evaluation.operands.left_to_right` |
| print_values_semantics | PrintValues | `output.print.evaluate_before_write`, `output.print.space_join_newline` |
| sequence_slice | SliceValue | `slice.evaluate_source_bounds_once_in_order`, `slice.list.shallow_outer_copy`, `slice.python_indices_and_zero_step`, `slice.string.unicode_codepoints` |
| string_membership_semantics | StringContains | `membership.negated`, `membership.string.unicode_substring` |
| unbound_call_order | Call, FunctionValueCall | `call.arguments.left_to_right`, `function_value.callee_before_arguments` |
| variadic_function_binding | FunctionDefinition, FunctionCall | `call.variadic.tuple_binding`, `function.variadic.tuple_binding` |
| with_context_management | With | `context.with.enter_exit_exception` |

## MODES

呼び出しの方式（Composition/Structural）はこの表と独立。
意味射影のメタデータはArtifactへ自動付加しない。

title: 判断表

semantics and admission:

| モード | 必須検査 | 実装者の責任 |
| --- | --- | --- |
| preservation（既定） | Model受理 + supports照合 | 意味保存を実行検証し、できないケースを拒否 |
| projection | Model受理のみ。実行意味のsupports照合なし | 抽出対象・保証範囲と誤った射影の拒否をTarget側でテスト |
