<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/target_implementation/declaration_reference.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# Realization Declaration Reference

適用先は `pyinto.realizations.regulation` のShikumi宣言API。
Packは**クラス名ではなく** `RealizationRegistry.from_pack(Pack)` に渡されたクラスの宣言で識別される。
実装前に[Implementation Guide](implementation-guide.md)と合わせて読む。

## API_001

Target識別子。名前に対応したTargetの自動探索は行われない。

name: pack_target

kind: Value

input: 空でないstr。例: pack_target @= 'outline'

## API_002

実際に登録するRealizationや型表現クラスの列挙。空のPackから規則は推測されない。

name: pack_entries

kind: Value

input: tuple[type, ...]。例: pack_entries @= (MyRealizer,)

## API_003

選択した呼び出しモードをPack全体へ適用する。混在はできない。

name: pack_dispatch

kind: Value

input: 'composition'（省略時）または'structural'

## API_004

実行意味の保存を求めるか射影のみかを定義する。成果物にメタデータは自動付加しない。

name: pack_semantics

kind: Value

input: 'preservation'（省略時）または'projection'

## API_005

登録対象と一致しないConstructの扱い。`traverse`では子は引き続き走査するが、そのノードのVisitorを実行しない。

name: pack_unhandled

kind: Value

input: 'error'（省略時）または'traverse'

detail: 'traverse' を使用できるのは structural + projection のみ

## API_006

要求ごとに新規Sessionを作る引数なしファクトリ。Structuralでは必須。

name: pack_session

kind: Value

input: Callable[[], object]。例: pack_session @= MySession

detail: 省略可能なCompositionでは既定TextArtifactSessionを使用

## API_007

Modelの**公開要素オブジェクト**を渡す。文字列名ではない。Construct、対応するbuiltin Call、Model型表記が対象。

name: @realizes(element)

kind: Operation

input: 例: @realizes(lang.FunctionDefinition)

detail: namingとの同時指定を禁止。Constructの派生型は自動一致しない（厳密なtype選択）

## API_008

Constructのvariant選択。省略時は`default`を意味し、全variantにはならない。

name: variant

kind: Value

input: 既知のvariant、または '*'。例: variant @= 'integer'

detail: '*'は任意の将来variantにも一致。個別指定が優先し、同一キー重複は拒否, 既知のvariant_domainでは存在しない名前を登録時に拒否, Structural+Projectionでは、複数variantまたは開いた定義域の省略を拒否

## API_009

Compositionで用いる静的Template。Slotの初出により子の合成を要求する。

name: template

kind: Value

input: 例: template @= '${body}'

detail: 同一Realization上でrender/visitと併用不可

## API_010

Compositionで用いる動的Layoutの選択関数。`TemplatePlan`で追加Slotも供給できる。

name: render

kind: Operation

input: Callable[[Construct, EmitContext], str | Text | TemplatePlan]

detail: 同一Realization上でtemplate/visitと併用不可

## API_011

Structural走査で用いる処理関数。成果物は戻り値でなくctx.sessionへ反映する。

name: visit

kind: Operation

input: Callable[[Construct, EmitContext], None]

output: Noneのみ（非Noneは拒否）

detail: 同一Realization上でtemplate/renderと併用不可

## API_012

Preservationで、Model側Admissionが要求する契約をRealization側がサポートすると宣言する。

name: supports

kind: Value

input: tuple[str,...] の一意な名前空間付き契約名。例: ('evaluation.operands.left_to_right',)

detail: Projectionでは実行意味のrequired_contracts照合を要求しないが、登録済みModelの検証は行う

## API_013

Composition実装の補助宣言。C/Python参照Realizerには例がある。

name: requires / separators / accepts

kind: Value

detail: requires @= 'name' は要求ヘッダー名の登録。separators @= {slot: sep} はJoined Slotの区切り, accepts @= (kind_name, ...) は直接builtin Callの引数種別制限

## API_014

Model型の文字列表現とターゲットの名前変換規則。

name: type_name / @naming / reserved / forbidden_prefixes / requirement_line

kind: Value

detail: type_name は文字列またはCallableの型表記。@namingはrealizesと排他, reserved/forbidden_prefixes は名前検証、requirement_lineは${name}のみ許す

## API_015

検証済みのPackを読み込む。存在しない宣言や重複はValueErrorとして拒否する。

name: RealizationRegistry.from_pack(Pack)

kind: Operation

input: 明示的に選んだPackクラス

output: RealizationRegistry

## API_016

PythonソースからModelを作ってTargetへ渡す。必須のrealizationsは省略不可。

name: pyinto.convert(source, *, realizations, interface_mappings=None, intrinsics=None, admission=None)

kind: Operation

output: Session.finish()が返す任意のobject

detail: 未登録ModelのチェックはRealizer/Session呼び出し前に実行する

## API_017

すでに構築されたModelをRealizeする。

name: pyinto.realize(program, *, realizations, admission=None)

kind: Operation

output: Session.finish()が返す任意のobject

## API_018

Realization呼び出し時の情報。入力Constructの変更は禁止。

name: EmitContext

kind: Type

output: root / current / parent / ancestors / path / registry / admission / session

detail: pathはroot始まりでcurrentを含む。fresh(stem)は補助名を生成する, sessionはTarget所有の現在の状態。headersはCompositionの要求名集合

## API_019

全Sessionに必要な最終提出メソッド。

name: Session.finish()

kind: Operation

output: 成果物（任意の型）。Hostは解釈・文字列化しない

detail: RealizationHostは要求単位でSessionを作成する

## API_020

Composition時にHostから最後に呼ばれるSessionメソッド。

name: Session.accept_composition(layout, context)

kind: Operation

input: 接続済みLayoutとEmitContext

detail: TextArtifactSessionはこの呼び出しでLayoutを保持し、finish時に文字列化

## API_021

有限定義域はfrozenset[str]、拡張可能な型はNoneを返す。

name: Construct.variant_domain()

kind: Operation

output: frozenset[str] | None

detail: 正確な一覧はConstruct/Variant Reference参照
