"""Public Target declarations and execution context reference."""

from shikumi_devdoc.fields.api_reference import (
    OPERATION,
    TYPE,
    VALUE,
    detail,
    input,
    kind,
    name,
    output,
)
from shikumi_devdoc.norms.common import canonical_source, summary


@summary(
    "Pack/Realization/Sessionの公開宣言・既定値・制約・結果を正確に参照するAPI辞典。"
)
@canonical_source(
    "Realization Declaration Reference",
    filename="declaration-reference.md",
    order=20,
    heading="identity",
    merge_policy="local",
)
class DECLARATION_REFERENCE:
    """適用先は `pyinto.realizations.regulation` の宣言API。宣言は通常のクラス属性（`=`）として書き、役割は `@realizes(element)` または `@naming` デコレータで示す。
    Packは**クラス名ではなく** `RealizationRegistry.from_pack(Pack)` に渡されたクラスの宣言で識別される。
    宣言として読むのはそのクラス自身の本体（`vars(cls)`）だけである。下表にない公開名（綴り誤りを含む）、型の合わない値、宣言クラスからの継承は登録時に `ValueError` として拒否する。`_` で始まる名前とdunderは宣言として扱わないため、補助属性には先頭に `_` を付ける。
    `render` や `visit` は `def render(node, context): ...` のようにクラス本体で直接定義してもよい。dictの値は `typing.ClassVar` 注釈を付けても受け付ける。関数内でクラスを定義する場合、`entries = entries` のように同名の外側変数は参照できない（Pythonのクラス本体のスコープ規則）ため、別名の変数を使う。
    実装前に[Implementation Guide](implementation-guide.md)と合わせて読む。
    """

    class API_001:
        """Target識別子。名前に対応したTargetの自動探索は行われない。"""

        name @= "target"
        kind @= VALUE
        input @= "空でないstr。例: target = 'outline'"

    class API_002:
        """実際に登録するRealizationや型表現クラスの列挙。空のPackから規則は推測されない。"""

        name @= "entries"
        kind @= VALUE
        input @= "tuple[type, ...]。例: entries = (MyRealization,)"

    class API_003:
        """選択した呼び出しモードをPack全体へ適用する。混在はできない。"""

        name @= "dispatch"
        kind @= VALUE
        input @= "'composition'（省略時）または'structural'"

    class API_004:
        """実行意味の保存を求めるか射影のみかを定義する。成果物にメタデータは自動付加しない。"""

        name @= "semantics"
        kind @= VALUE
        input @= "'preservation'（省略時）または'projection'"

    class API_005:
        """登録対象と一致しないConstructの扱い。`traverse`では子は引き続き走査するが、そのノードのVisitorを実行しない。"""

        name @= "unhandled"
        kind @= VALUE
        input @= "'error'（省略時）または'traverse'"
        detail @= "'traverse' を使用できるのは structural + projection のみ"

    class API_006:
        """要求ごとに新規Sessionを作る引数なしファクトリ。Structuralでは必須。"""

        name @= "session"
        kind @= VALUE
        input @= "Callable[[], object]。例: session = MySession"
        detail @= "省略可能なCompositionでは既定TextArtifactSessionを使用"

    class API_007:
        """Modelの**公開要素オブジェクト**を渡す。文字列名ではない。Construct、対応するbuiltin Call、Model型表記、Kindの要素が対象。"""

        name @= "@realizes(element)"
        kind @= OPERATION
        input @= "例: @realizes(lang.FunctionDefinition)"
        detail @= "namingとの同時指定を禁止。Constructの派生型は自動一致しない（厳密なtype選択）"

    class API_008:
        """Constructのvariant選択。省略時は`default`を意味し、全variantにはならない。"""

        name @= "variant"
        kind @= VALUE
        input @= "既知のvariant、または '*'。例: variant = 'integer'"
        detail @= "'*'は任意の将来variantにも一致。個別指定が優先し、同一キー重複は拒否"
        detail @= "既知のvariant_domainでは存在しない名前を登録時に拒否"
        detail @= "Structural+Projectionでは、複数variantまたは開いた定義域の省略を拒否"

    class API_009:
        """Compositionで用いる静的Template。Slotの初出により子の合成を要求する。"""

        name @= "template"
        kind @= VALUE
        input @= "例: template = '${body}'"
        detail @= "同一Realization上でrender/visitと併用不可"

    class API_010:
        """Compositionで用いる動的Layoutの選択関数。`TemplatePlan`で追加Slotも供給できる。"""

        name @= "render"
        kind @= OPERATION
        input @= "Callable[[Construct, EmitContext], str | Text | TemplatePlan]"
        detail @= "同一Realization上でtemplate/visitと併用不可"

    class API_011:
        """Structural走査で用いる処理関数。成果物は戻り値でなくctx.sessionへ反映する。"""

        name @= "visit"
        kind @= OPERATION
        input @= "Callable[[Construct, EmitContext], None]"
        output @= "Noneのみ（非Noneは拒否）"
        detail @= "同一Realization上でtemplate/renderと併用不可"

    class API_012:
        """Preservationで、Model側Admissionが要求する契約をRealization側がサポートすると宣言する。"""

        name @= "supports"
        kind @= VALUE
        input @= "tuple[str,...] の一意な名前空間付き契約名。例: ('evaluation.operands.left_to_right',)"
        detail @= "Projectionでは実行意味のrequired_contracts照合を要求しないが、登録済みModelの検証は行う"

    class API_013:
        """Composition実装の補助宣言。C/Python参照Realizerには例がある。"""

        name @= "requires / separators / accepts"
        kind @= VALUE
        detail @= "requires = ('name', ...) は要求ヘッダー名の登録（strのtuple。文字列単体は拒否。型表記にも付けられる）。separators = {slot: sep} はJoined Slotの区切り"
        detail @= "accepts = (kind_name, ...) は直接builtin Callの引数種別制限"

    class API_014:
        """Model型の文字列表現とターゲットの名前変換規則。"""

        name @= "type_name / @naming / reserved / forbidden_prefixes / requirement_line"
        kind @= VALUE
        detail @= "type_name は文字列またはCallableの型表記。@namingはrealizesと排他"
        detail @= (
            "reserved/forbidden_prefixes は名前検証、requirement_lineは${name}のみ許す"
        )

    class API_015:
        """検証済みのPackを読み込む。未知の宣言名、型の誤り、存在しない宣言や重複はValueErrorとして拒否する。"""

        name @= "RealizationRegistry.from_pack(Pack)"
        kind @= OPERATION
        input @= "明示的に選んだPackクラス"
        output @= "RealizationRegistry"

    class API_016:
        """PythonソースからModelを作ってTargetへ渡す。必須のrealizationsは省略不可。"""

        name @= "pyinto.convert(source, *, realizations, interface_mappings=None, intrinsics=None, admission=None)"
        kind @= OPERATION
        output @= "Session.finish()が返す任意のobject"
        detail @= "未登録ModelのチェックはRealization/Session呼び出し前に実行する"

    class API_017:
        """すでに構築されたModelをRealizeする。"""

        name @= "pyinto.realize(program, *, realizations, admission=None)"
        kind @= OPERATION
        output @= "Session.finish()が返す任意のobject"

    class API_018:
        """Realization呼び出し時の情報。入力Constructの変更は禁止。"""

        name @= "EmitContext"
        kind @= TYPE
        output @= "root / current / parent / ancestors / path / registry / admission / session"
        detail @= "pathはroot始まりでcurrentを含む。fresh(stem)は補助名を生成する"
        detail @= "sessionはTarget所有の現在の状態。headersはCompositionの要求名集合"

    class API_019:
        """全Sessionに必要な最終提出メソッド。"""

        name @= "Session.finish()"
        kind @= OPERATION
        output @= "成果物（任意の型）。Hostは解釈・文字列化しない"
        detail @= "RealizationHostは要求単位でSessionを作成する"

    class API_020:
        """Composition時にHostから最後に呼ばれるSessionメソッド。"""

        name @= "Session.accept_composition(layout, context)"
        kind @= OPERATION
        input @= "接続済みLayoutとEmitContext"
        detail @= (
            "TextArtifactSessionはこの呼び出しでLayoutを保持し、finish時に文字列化"
        )

    class API_021:
        """有限定義域はfrozenset[str]、拡張可能な型はNoneを返す。"""

        name @= "Construct.variant_domain()"
        kind @= OPERATION
        output @= "frozenset[str] | None"
        detail @= "正確な一覧はConstruct/Variant Reference参照"

    class API_022:
        """Runtime情報経路の利用宣言。Dispatch/Semanticsとは独立であり、省略した既存Packは無視する。"""

        name @= "runtime"
        kind @= VALUE
        input @= "'required' / 'forbidden' / 'optional' / 'ignored'（既定）"
        detail @= "required: 関数必須・実行してfinish(R)。forbidden: 存在を拒否。optional: あれば実行してfinish(R)、なければfinish(RUNTIME_ABSENT)。ignored: 存在は許可し、実行せずfinish()。required/optionalではカスタムSessionが必須。"

    class API_023:
        """静的な構造と実行時の値をSession確定時に統合する。Runtime関数が戻した任意のオブジェクトの型と意味はTargetが検証する。"""

        name @= "__pyinto_runtime__() / RUNTIME_ABSENT / Session.finish(R)"
        kind @= OPERATION
        input @= "信頼済み入力モジュールに同期・無引数のトップレベルdefを宣言。RUNTIME_ABSENTはpyinto.realizationsからimport。"
        output @= "Runtimeがあるrequired/optionalでは戻り値R。optionalで関数がない場合はRUNTIME_ABSENT。"
        detail @= "realize(model)はソースを持たずrequiredでは拒否。Runtimeが不要なTargetのSessionは従来のfinish()を維持。"

    class API_024:
        """Runtime Resultの値と型に対するTarget定義のスキーマ。省略時はHostによるRのスキーマ検査なし。"""

        name @= "runtime_schema"
        kind @= VALUE
        input @= "type | Callable[[object], bool]。例: runtime_schema = ResultType または runtime_schema = validate_result"
        detail @= "required/optionalでのみ宣言可能。typeは単純なisinstance判定。list[int]等のジェネリック式とUnion式は不可。複雑な型・値の条件は検証関数で表す。"
        detail @= "検証関数の引数はRひとつで、戻り値は厳密なbool。偽、不正戻り値、検証例外はRuntimeSchemaErrorとなり、Session.finish()を呼ばない。optionalの不在時は検証せず、Noneは検証する。"

    class API_025:
        """Kind の型の語ごとの型表記の登録対象。ソース側の `pyinto.kinds` ではなく、同じ構成の `pyinto.model.kinds` の要素を使う。"""

        name @= "@realizes(dd.Int) など（from pyinto.model.kinds.datatypes import detailed as dd）"
        kind @= OPERATION
        input @= "datatypes.general: Wide / Narrow / Unsigned / Size / Index / Byte。datatypes.detailed: Int / UInt / Float / Decimal / CodeUnit / Array / Enum / Function / Char / Void / Nil / Null。memory.general: Owned / Shared / Buffer。memory.detailed: Pointer / Ref"
        detail @= "type_name の動的表記は shape.label（KindLabel(name, arguments)）を読み、入れ子は spell(shape.label.arguments[0]) で表記する。Wide / Narrow / Unsigned は profile(shape) で読み替えられる"
        detail @= "未登録の語は種別の表記へ置き換えず拒否する。値の Void / Nil / Null は lang.NoneAlias の variant（void / nil / null）、ポインタ操作は lang.AddressOf / PointerLoad / PointerStore、None別名の比較は lang.NoneAliasComparison で実現する"
        detail @= "クラスに付けた @Interface / @MixIn / @Implements は ClassDefinition.labels から読む"
        detail @= "動的メモリの操作は lang.MemoryNew / MemoryNewBuffer / MemoryRelease / MemoryResize / MemoryLength / MemoryBorrow / MemoryCopy / MemoryFill で実現する。MemoryRelease と MemoryBorrow は variant（single / buffer）で単体と列を区別できる"

    class API_026:
        """Target 実装を支える Kind の補助関数。"""

        name @= "pyinto.model.kinds.profile(value_type) / missing_general(registry)"
        kind @= OPERATION
        output @= "profile: NumericProfile(base, rank, unsigned) または None。missing_general: 未登録の汎用語彙名の tuple"
        detail @= "profile は Unsigned[Wide[Wide[int]]] を (INTEGER, 2, True) と読む。Wide / Narrow / Unsigned 以外のラベルは None"
        detail @= "missing_general は基準の型（int / float / str / bool / None / list / dict / tuple / Callable / class）、general の型の語、メモリの汎用操作の Construct を調べる。汎用語彙への対応を表明する Target はテストで空であることを確かめる"

    class API_027:
        """型表記の要求名と、描画関数からの型の表記。"""

        name @= "requires（型表記）/ EmitContext.type_name(model_type)"
        kind @= OPERATION
        input @= "例: @realizes(dg.Size) のクラスに requires = ('stddef.h',) と type_name = 'size_t'"
        detail @= "Slot の型が使う表記の要求名は合成時に集められ、requirements に含まれる。描画関数で型を表記するときは EmitContext.type_name() を使う"
