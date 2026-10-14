"""Current validated Realization Registry, mechanical Composer and Renderer."""

from shikumi_devdoc.fields.specification import INFORMATIVE, MUST, level, related
from shikumi_devdoc.norms.common import canonical_source, summary
from shikumi_devdoc.norms.document import title

from devdocs.canonical_sources.specification.construct import (
    SPECIFICATION_PART as CONSTRUCT_SPEC,
)


@summary(
    "Realization API による実現規則の解決、Template／Slot 合成、Render の実装済み規則。"
)
@canonical_source(
    "Composition",
    filename="composition.md",
    order=30,
    merge_policy="local",
    heading="identity",
)
class SPECIFICATION_PART:
    """RealizationRegistryによる現行の検証可能な合成契約を記す。"""

    class CMP_001:
        """現行 `RealizationRegistry` は Shikumi 宣言を検証し、Construct の厳密な型と `variant()`、または Call の登録名から対応するレシピを解決する。公開要素を渡す `@realizes(element)` も同じ経路へ接続する。対象はConstructクラス、`builtin.PrintCall` の直接 Call、`ValueKind` / `PortType` の型表記であり、`PrintCall` と `PrintValues` は別の対象である。全組み込み操作の直接Call対応は実装していない。宣言クラスは `@realizes(element)` または `@naming` の一方だけを持ち、未登録対象や同一対象の重複を拒否する。未登録・無効な公開要素・重複などの不正な規則を黙示的な NOOP で補わず拒否する。"""

        title @= "宣言の検証と実現規則の解決"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_001,)

    class CMP_002:
        """Composer は Template 中に現れた Slot を初出順で一度ずつ合成し、対応する子 Construct の実現を再帰的に接続する。同じ Slot が Template に複数回現れても、その Slot の子の合成結果を再利用する。子は合成中に最終ソース文字列へ変換しない。"""

        title @= "Template／Slot の再帰的な遅延合成"
        level @= MUST

    class CMP_003:
        """Slot に対応する名前付き子要素がない場合、非葉の Construct に `Text` のみを返す場合、または不正な Layout 要素を渡した場合はエラーとする。Template が参照しない子要素は現行 Composer では自動的に合成されない。"""

        title @= "Slot の実装済み検証範囲"
        level @= MUST

    class CMP_004:
        """選択コールバックには `EmitContext` が渡り、構成中の `root`、`current`、`parent`、`ancestors`、`path` を参照できる。これらは元 Construct への参照であり、Realization は元の構造を書き換えないという規約に従う。クロージャー等による強制的な読み取り制限は設けない。"""

        title @= "構造情報の広い読み取りアクセス"
        level @= MUST

    class CMP_005:
        """独立した合成要求ごとに `EmitContext` の補助名カウンタと requirements 集合を初期化する。Template の Slot 初出順に従った `fresh()` の命名と、要求ヘッダのソートされた出力によって、同一の決定論的な実現規則から再現可能な出力を得る。"""

        title @= "合成要求の生成状態を分離"
        level @= MUST

    class CMP_006:
        """Renderer は接続済み Layout を最終段階で文字列化する。複数行の Slot 展開は、その Slot が Template の独立した行にある場合に限り許容し、親行のインデントを各行へ反映する。行中に配置する Slot が複数行へ展開されるときは拒否する。"""

        title @= "最終文字列化と複数行 Slot"
        level @= MUST

    class CMP_007:
        """Template に参照されない子 Construct を出力すべきかどうかについて、現在は一般的な網羅性検証を設けていない。今後 Realization の責務と省略契約を整理する際の設計課題であり、現行実装に網羅性保証があるという宣言ではない。"""

        title @= "未参照の子の網羅性は未確定"
        level @= INFORMATIVE

    class CMP_008:
        """Composer は Model 由来の `Identifier` を Target 側の名前検証付き Layout、`Symbol` の `type` および `ValueType` / `PortType` を完全な型情報のまま型表現 Layout、Construct の順序付き `tuple` を Joined Layout へ機械的に変換する。型を表す Layout は子要素型・戻り型・公称型の詳細を欠落させない。`requirements` は Program の構造ではなく出力用の予約 Slot として Realization 側で充足する。"""

        title @= "Model 部品から Layout への境界変換"
        level @= MUST

    class CMP_009:
        """変換 API は指定された `RealizationRegistry` をそのまま使用し、言語名による標準 Target Pack の暗黙選択を行わない。`realize` は引数の Construct を選択したTarget Packの実行方式でRealizeし、Target Sessionの成果物を返す。`convert` はFrontend正規化の後で同じ経路を通す。Composer.source() は既存のTemplate/Slotの文字列合成ユーティリティとして維持する。"""

        title @= "明示的に選択した実現規則での変換"
        level @= MUST

    class CMP_010:
        """動的 Realization は `TemplatePlan`（Template の文字列と Realization が供給する名前付き Slot 部品）を返せる。Composer は Construct 自身の `parts()` と Realization 供給 Slot を衝突なく統合し、Template に現れる Slot を初出順で再帰合成する。Slot 値は最終文字列ではなく Model / Layout 部品として接続する。モデル部品の上書き・未充足 Slot・未使用の供給 Slot は明示的に拒否する。"""

        title @= "Realization 提供 Slot の機械的な接続"
        level @= MUST

    class CMP_011:
        """`requirements` は `Program` のみが出力に利用できる Composition 所有の予約 Slot であり、Shikumi 宣言検証は `Program` の Template に限ってその名前を受理する。その他の Construct に同じ Slot を置く、または未定義 Slot を置く静的 Template は拒否する。"""

        title @= "Program 出力専用 Slot の静的検証"
        level @= MUST

    class CMP_012:
        """静的な Template 宣言の Slot 名は、Model が公開しうる名前（`accepts_part_name()`）と Composition 所有の予約名で検証する。動的に存在しうる番号付き要素はクラスで宣言できるが、選択された Construct インスタンスが持たない Slot は合成時に拒否する。Realization は未存在の Model 要素を暗黙に生成しない。"""

        title @= "Model 要素と Slot の二段階検証"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_013,)

    class CMP_013:
        """Target Pack の実現宣言は、`@realizes(element)` で対象を選び、
        Constructについては必要に応じて `variant` を指定した後、
        `supports` に宣言した名前付き意味契約と、
        対象 Construct インスタンスから機械的に導いた必須契約を照合する。
        対応を宣言していない必須契約がある場合、`render` コールバック実行や
        requirements の収集より前に `ConstructError` で拒否する。

        第15回の検査対象は関数・コンストラクタ・メソッド等の直接呼出に限り、
        仮引数への束縛順、ソース評価順の並び替え、省略された既定引数、
        VIRTUAL / SUPER のディスパッチと SUPER のレキシカル探索起点、
        クラス Receiver の実行時同一性を個別の契約名として扱う。
        短絡、反復形式、例外制御、環境寿命等の契約については **まだ未実装**。
        `supports` は Realization 作者による明示的な対応宣言であり、
        Template/Renderer の意味保存を自動証明するものではない。
        宣言の欠落を拒否することと、宣言内容の実装・実行検証は区別する。
        """

        title @= "Realization の意味契約への適用条件（初期実装）"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_001,)

    class CMP_014:
        """第16回では、引数束縛を持つ5種の直接呼出について、`supports` 宣言の
        有無とは独立に、文字列Template（静的宣言または `render` が返した文字列）を
        合成する直前に、呼出元で明示された実引数の `${argN}` Slot がそれぞれ
        ちょうど1回現れること、またそれらがソース評価順に現れることを確認する。
        省略済みの不変スカラーデフォルトに対応する Slot は、省略または出力してよい。
        違反時は `ConstructError` で拒否する。これは単純なSlot展開の取りこぼしや
        順序変更を検出するための保守的な構文検査であり、実行順序・束縛・dispatch
        の意味保存を証明するものではない。

        `TemplatePlan` によるRealization供給Slotや任意のTarget展開はこの検査の
        対象外とし、個別のTarget上の実行検証で意味保存を確認する。
        Model の型・構造・既存のFrontend受理条件は変更しない。
        """

        title @= "直接呼出の単純なTemplateに対するSlot使用と順序の検査"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_001,)

    class CMP_015:
        """第17回では `IterationEntry` と `For` の実現規則選択時に、
        反復元の既知の構造型（`range` / `string` / `list` / `tuple`）または
        未整形の `iterable` を `iteration.source.<kind>` という必須契約へ分類する。
        登録済み Realization の `supports` に該当する形式がない場合は、
        `render` を実行する前に拒否する。`For` 全体を独自に展開する
        `TemplatePlan` でも入口の子要素を合成しない場合があるため、
        `For` 自体にも契約を適用する。C の標準 Pack は `range` のみ、
        Python の標準 Pack は range / string / list / tuple と汎用 iterable の
        構文展開を宣言する。PythonFrontend の受理は FRT_003 の範囲に限る。
        これらの宣言は、反復元の一回評価・ループ中の制御フロー・生成コードの
        意味保存を形式的に証明するものではない。
        """

        title @= "反復元の種類に応じた Realization 適用の判定"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_004,)

    class CMP_016:
        """Realizationの受理条件は、Construct提供者の`AdmissionDeclaration`に含まれる
        `AdmissionRule`から導出する。`AdmissionRule`は対象Construct型、監査対象フィールド、
        契約識別子（末尾`.*`による開いた系列を含む）、必須契約の抽出規則を保持する。
        未登録の具体的Constructは明示的に拒否する。

        `AdmissionRegistry.extend(...)`は新しいConstruct提供者の宣言を追加できるが、
        既存の契約登録を置換しない。合成に利用する基準契約台帳は
        `require_baseline()`で削除・置換を拒否する。`RealizationRegistry`と
        `RealizationRegistry.from_pack()`はConstructの意味契約を独自に登録しない。
        レシピ選択時にはConstructが要求する具体的な契約名と、Target側の
        `supports`宣言を照合し、不足があれば描画前に拒否する。`supports`に
        ワイルドカードを用いて一括承認することはできない。

        既存規則が提供する契約だけが機械的照合の対象となる。
        契約未宣言・`pending`の意味保存を保証したことにはならない。
        """

        title @= "Realization受理規則の宣言的な構成と拡張"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_001,)

    class CMP_017:
        """5種の束縛済み直接呼出は、仮引数への束縛の正当性
        `call.arguments.bound` と、呼出元で明示された実引数の評価順序を
        **別の契約**として扱う。明示引数が2個以上ある場合、仮引数順への
        並べ替えの有無にかかわらず `call.arguments.left_to_right` を要求する。
        明示引数の評価順が対応する仮引数の昇順と異なる場合に限って、
        さらに `call.arguments.reordered` を要求する。省略され、既定値で
        補完された引数は「明示的に評価される実引数」の数に含めない。
        省略引数自体の扱いは従来どおり `call.defaults.omitted` を要求する。

        この規則は **Model に Target 固有の評価規則を追加しない**。
        Frontend が保持した評価順という既存の意味契約を
        Realization 側が満たせるか、Target ごとに宣言・検証する。
        CMP_014 の文字列 Template に対する Slot 出現順検査は、
        Target の実行時の評価順序を保証するものではない。
        Target によって引数評価順が異なる、または未規定の場合は、
        対応する Realization が必要な一時変数等を用意する責務を持つ。
        `supports` 宣言だけで意味保存を証明したことにはならない。
        この段階では 5種以外の値式・Port 呼出や演算子の一般評価順は
        未保護であり、監査台帳の `pending` として扱う。
        """

        title @= "束縛済み直接呼出の評価順契約とTarget実現責務"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_001,)

    class CMP_018:
        """第20回から、Construct の意味契約登録は Target から独立した
        `AdmissionDeclaration` と `AdmissionRegistry` が所有する。
        Language Constructは`LANGUAGE_ADMISSION`に種類ごとに明示登録し、独自のConstructを
        提供するライブラリは、`AdmissionRule` または空の規則集合を
        明示して拡張する。未登録の具体型は、既知の型の派生クラスを含めて
        拒否する。空の宣言と登録漏れは区別し、空の宣言で意味保存を
        証明したとは扱わない。基準台帳の宣言は
        `AdmissionRegistry.require_baseline()`により外部からの削除・置換を拒否する。

        `realize()` は提供者の `admission` を明示的に受け取れる。
        `convert()` は明示された `InterfaceMappingRegistry` の契約登録を利用し、
        `RealizationRegistry` / Target Pack は Construct の契約を自分で追加しない。
        追加Interfaceを使用しない場合には既定の`LANGUAGE_ADMISSION`を用いる。
        Composer は開始時に元Modelの `parts()` 経由で到達できるConstructを
        走査し、Templateが参照しない子であっても未登録の具体型なら
        拒否する。受理規則の照合は個別レシピ選択後・描画前に行う。

        この段階で無条件に全子要素を出力する義務は追加しない。
        `parts()` から到達できない文脈情報や、未保護の `pending` 契約も
        残る。Target上の意味保存を自動証明する仕組みではない。
        """

        title @= "Construct提供者の契約登録と未登録Modelの拒否"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_001,)

    class CMP_019:
        """第21回では `For` の `break` / `continue` によるループ制御と、
        `else_body` が存在する場合の break を伴わない正常完了だけによる
        `else` 実行を、Target非依存の `for_control_flow` 受理規則とする。
        `For` は必ず `loop.for.break_continue` を要求し、
        `else_body` がある場合だけ `loop.for.normal_completion_else` を
        追加する。`With` は個数やネストに依存せず、entryの入場順、
        逆順の退出、例外時の退出と抑制を包含する
        `context.with.enter_exit_exception` を要求する。

        C Target Implementationのrangeループと、非公開の開発用Python
        Realizerのfor・withは、
        自身の実現規則に対応する `supports` を明示する。宣言が
        不足するRealizationは render/ヘッダ要求より前に拒否する。
        受理の自己宣言のみでTargetの実行意味が保証されるわけではなく、
        break/continue/elseと例外時の入退場順はTargetで実行検証する。
        新しいModelフィールドやTarget固有の実現戦略は追加しない。
        標準Packで使用する `Comparison` の評価順序は現時点では
        `pending` のままであり、別工程で対応を検討する。
        """

        title @= "ForとWithの制御フローをRealizationの受理条件へ接続"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_001,)

    class CMP_020:
        """既存の型付き二項式 `Arithmetic`、`Comparison`、`FloatingArithmetic`、
        `FloatingComparison` と文字列関連の二項式について、左右（または
        source / index）のValueを定義された順で評価する義務を
        `evaluation.operands.left_to_right` として要求する。Port `Call`は
        実引数が2つ以上なら `call.arguments.left_to_right` を要求し、
        `FunctionValueCall`は同じ条件に加えて実引数がある場合
        `function_value.callee_before_arguments` を要求する。
        ModelにTarget言語の評価順や副作用解析を追加しない。

        単純な文字列Templateでは対象の各Value Slotをちょうど一度使用し、
        ソース上の順序で記述することを確認する。`TemplatePlan`による
        派生Slotへの展開はこの機械検査の対象外とし、Target固有の検証を要する。
        Slotの文字順は実行順の保証ではなく、`supports`も宣言であり証明ではない。
        C標準Comparison Realizationは順序を保証できない複合被演算子の
        組み合わせを拒否し、単純な参照・定数の比較等に限る。
        未登録のRealizationは従来どおり拒否する。
        """

        title @= "型付き二項式・Port/関数値呼出の評価順受理と直接Slot検査"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_001,)

    class CMP_021:
        """命名規則はShikumiの引数なしマーカー `@naming` で宣言する。
        このマーカーは命名ポリシーを登録し、識別子の予約語・禁止プレフィックス・
        生成要件書式（`reserved` / `forbidden_prefixes` / `requirement_line`）を
        `@=` で指定する。`@naming` と `@realizes(element)` は同じクラスで
        併用できない。Target内の命名規則の重複、いずれのマーカーもない宣言、
        `requirement_line` で `${name}` 以外のSlot、Namingに付けた
        `supports` は拒否する。Host、C Target、開発用Python Realizerには
        一つの宣言体系のみ存在し、過去の宣言形式を受け入れる経路は持たない。
        """

        title @= "NamingマーカーとRealization宣言の排他性"
        level @= MUST

    class CMP_022:
        """`RealizationRegistry.type_name()` は `Symbol`、`ValueType`、`PortType` を受け取り、Model上の型情報の完全な形状を型表記Selectorへ渡す。`@realizes(vt.List)` 等のRealization選択は従来どおり大分類 `ValueKind` を使うが、動的 `type_name @= callable` は具体的な再帰的 `ValueType` を受け取る。Port型のSelectorは従来どおり完全な `PortType` を受け取る。Targetは複合型ごとの表記を選択し、同一の表記を共有しても、実現できない型を拒否してもよい。文字列の型表記に対しては固定表記を維持し、対応型がない場合や空・非文字列の結果を拒否する。`FunctionDefinition.parts()` / `HOLES` には署名の `return_type` を完全な `ValueType` として追加する。`Parameter`、`Initialize`、`FieldDefinition` 等の `type` Slot と同じ型表記経路を利用し、ModelからTargetの型記法を指定しない。"""

        title @= "複合型と戻り値型を欠落させない型Slotと型表記"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_001,)

    class CMP_024:
        """動的な型表記 `type_name @= callable` は `(shape, spell)` の2引数を受け取る。
        `shape` は完全な `ValueType` または `PortType`、`spell` は同じTargetの
        `RealizationRegistry` に登録された型表記を再帰的に解決する関数であり、
        `Symbol`、`ValueType`、`PortType` を受理する。内側の型をPython表記へ
        暗黙変換せず、未登録なら拒否し、各階層の出力も非空文字列に検証する。
        一つの型表記要求の呼出し経路で同じ具体型を再要求した場合は
        `ConstructError` で循環を拒否する。独立した要求間ではガードを共有しない。
        型表記文字列の固定指定はそのまま利用できる。旧1引数の動的Selectorは
        新規約に移行し、自動的な引数個数判定や別の型対応表は設けない。
        Modelの型構造、Targetのサポート範囲、Slotの `separators` 規則は不変とする。
        """

        title @= "同じTarget規則による入れ子型表記と循環拒否"
        level @= MUST

    class CMP_023:
        """Realizationの `separators @= {"slot_name": "separator"}` は、Templateが参照するモデル由来の `tuple` Slotの要素間区切りをSlotごとに指定する。指定がない `tuple` は従来どおり改行区切りとし、空要素列は空文字列になる。要素の順番・個数を変更せず、遅延合成と最終描画でのみ結合する。Slot以外の名前、未参照Slot、文字列以外の区切り、`tuple` ではない実際のModel部品への指定は拒否する。Templateのインライン複数行Slot禁止規則は維持する。末尾区切りや括弧、Target言語の構文妥当性はRealizationの責務であり、自動補完しない。"""

        title @= "Slot別のtuple結合文字列の指定"
        level @= MUST

    class CMP_025:
        """Target Packは`pack_dispatch @= "composition" | "structural"`（省略時はcomposition）と`pack_session @= callable`を宣言する。`composition`は既存Template/Slotの初出順連鎖、`structural`は`Construct.parts()`から到達する全Constructを深さ優先先行順で呼ぶ。実行方式はTarget Pack単位で選び、混在する`template`/`render`宣言と`visit`宣言を拒否する。structuralモードではSession factoryを省略できない。型情報等の非Construct部品は訪問対象にはならないが、元Modelから参照可能なままとする。"""

        title @= "Target Pack単位の呼出方式選択"
        level @= MUST

    class CMP_026:
        """StructuralのRealizationは`@realizes(element)`と`visit @= callable`で宣言する。Visitorには元のConstructと`EmitContext`を渡し、`ctx.session`にTarget所有の実行状態を公開する。Visitorの戻り値は`None`に限定する。`root/current/parent/ancestors/path`はCompositionと同じ意味の元Model参照であり、同じConstructが別の位置に現れた場合も位置ごとに訪問する。標準の`preservation` / `error`方針では未登録Realizer・未登録Admission・未サポートの必須意味契約を従来どおり拒否する。明示的な射影・走査方針の場合はCMP_028〜030に従う。"""

        title @= "構造順訪問とModel参照・受理契約"
        level @= MUST

    class CMP_027:
        """Targetが指定した`pack_session` factoryを実現要求ごとに一度呼び、各Realizerは`EmitContext.session`で状態にアクセスできる。Compositionは既存Composerの遅延LayoutをSessionの`accept_composition(layout, context)`へ渡し、Targetが`finish()`で最終的な成果物を提出する。テキストTargetは共通補助`TextArtifactSession`を選択できるが、非テキストの成果物形式・内部状態はTargetが自由に決める。StructuralではSessionの`finish()`だけを要求する。Hostは成果物の文字列化、ヘッダー/フッター専用Hook、ファイル保存を行わない。`Composer.source()`は単独の従来型テキスト合成APIとして利用可能とする。"""

        title @= "Target Sessionによる成果物の所有と提出"
        level @= MUST

    class CMP_028:
        """Target Packは`pack_semantics @= "preservation" | "projection"`を宣言でき、省略時は`preservation`とする。実行方針の`pack_dispatch`とは独立し、Registryからも同じ区別を参照できる。`preservation`では従来のAdmission必須実行意味契約とRealizationの`supports`宣言を照合する。`projection`は成果物の実行意味保存を主張しないため、この`supports`照合を要求しない。ただしConstruct提供者のAdmission登録・Baseline整合・`check_tree()`によるModel全体の受理確認は両モードで同一に行う。射影成果物の個別の情報正確性はTargetの責務であり、射影設定が意味的正しさを保証するわけではない。"""

        title @= "意味保存と意味射影の明示的な区別"
        level @= MUST

    class CMP_029:
        """`pack_unhandled @= "error" | "traverse"`は、宣言が存在しないConstructの訪問方針であり、省略時は`error`として明示拒否する。`traverse`は`pack_dispatch="structural"`かつ`pack_semantics="projection"`の場合だけ選択でき、Realizationが未登録の具体Construct型またはvariantについてVisitorを呼ばず、その`parts()`に含まれる子Constructへの深さ優先・親先の走査を維持する。登録済みVisitorの例外、不正な戻り値、Callの引数検証、循環検査は握りつぶさない。`traverse`はAdmission未登録のConstructを許可するものではなく、`check_tree()`はSession作成前にModel全体を検証する。保存型TargetとCompositionでの未処理通過は禁止する。"""

        title @= "射影Targetの未処理Construct明示通過"
        level @= MUST

    class CMP_030:
        """`pack_semantics`と`pack_unhandled`はTargetの契約メタ情報であり、Hostが提出された成果物に自動埋め込み・ラップするものではない。`convert`/`realize`は従来どおりSessionの`finish()`が返した任意型オブジェクトをそのまま返す。成果物内部のメタデータ形式・個別射影の正しさ・射影範囲の包括的宣言・Structuralの子訪問終了Hookは本工程では標準化しない。"""

        title @= "意味モードと成果物形式の独立性"
        level @= MUST

    class CMP_031:
        """Realization登録時、Constructの `variant_domain()` が有限集合を返すときは
        `variant @=` の具体値がその集合に属するか照合し、誤記を拒否する。
        variant指定がない場合は従来どおり `"default"` と解釈するが、
        当該Constructにdefault variantが存在しない場合は登録時に拒否する。
        `structural`かつ`projection`の場合、複数variantを持つConstruct
        および定義域が開いているConstructには、variantの明示指定を要求する。
        `variant @= "default"` はそのvariantだけ、`variant @= "*"` は
        任意variantに対する明示的な一致を意味する。`*` は登録時に既知候補へ
        展開せず、後から追加されたvariantも対象となる。
        同じConstructに具体指定と`*`が共存する場合は具体指定を優先する。
        同一Constructと同一variant（`*`を含む）の重複は引き続き拒否する。
        `*` が緩和するのはRealization選択範囲だけであり、preservationの
        Admission/`supports`検証と構造チェックを迂回しない。
        開いた定義域の具体キーは一覧との照合ができず、実行時選択に委ねる。
        Call・型表記・命名宣言にvariantを付けることは認めない。
        射影Targetの `traverse` は明示的に選んだvariant以外を従来どおり
        通過できるため、型に部分的なRealizerがあるというだけで
        他のvariantをエラー扱いにはしない。
        """

        title @= "variant定義域の事前検証とワイルドカード選択"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_075,)
