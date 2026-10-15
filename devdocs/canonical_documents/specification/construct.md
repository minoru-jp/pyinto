<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/specification/construct.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# Construct Model

段階的な Model 境界整理を反映した実装済み契約。

## CST_001

Construct は Python AST ではなく、正規化した操作と名前付き子要素を保持する。`parts()` は要素名から子要素への対応を公開し、`variant()` は実現規則を選択するための構造上の区別を返す。Construct 自身は `emit()` で生成コードを出力しない。

title: 正規化構造と子要素

level: MUST

## CST_075

Constructは `variant_domain()` によって、自身が返しうるvariantの
既知の有限集合を `frozenset[str]` として公開する。標準の `variant()`
だけを使用する型の定義域は `{"default"}` であり、variantを
上書きする組み込みConstructは `VARIANTS` に具体的な候補を記述する。
IntrinsicCallのように操作提供者の登録によりキーが拡張される場合は
`VARIANTS=None` とし、定義域が開いていることを明示する。
外部Constructがvariantを上書きしながら `VARIANTS` を宣言しない場合も
未知の定義域として扱う。この情報はTargetや成果物形式には依存せず、
Realizationの登録検証を支えるModel側のメタデータである。

title: Construct variantの定義域の公開

level: MUST

## CST_002

値を持つ `Symbol` は新規宣言時の型アノテーションを保持しなければならない。`Symbol.type` は通常の値宣言では再帰的 `ValueType` を1つ保持し、マップ済みオブジェクトでは `MappedType` を保持して、その source と variant を区別する。`MappedType` はコンストラクタ引数や数値の範囲・サイズを保持しない。組み込み専用シンボルは `type=None` とする。`kind` と各型形状の参照属性は `type` から読み取る派生情報であり、別々の保存フィールドではない。マップ済みオブジェクトと組み込み専用シンボルを一般の `ValueType` に暗黙変換しない。Python の型情報から Target 固有の型表現は決定しない。

title: 型とマップ済みオブジェクト形状の保持（現行Model名）

level: MUST

## CST_003

`Block` は順序付きの子 Construct を保持する。`Branch` と `While` は条件と本体を保持し、`else` がある場合だけ対応する子 Block を公開し、`variant()` を `with_else` とする。`Break` と `Continue` は独立した Construct である。

title: Block・分岐・ループの構造

level: MUST

## CST_004

`For` は `IterationEntry`（束縛先と反復元）、本体、任意の `else` Block だけを `parts()` で公開する。`Range` は整数型の1〜3引数をそのまま保持し、`bounds()` は Python の `range` 契約に従い既定の開始値 0 とステップ 1 を補う。`For` は特定の反復形式の開始値・停止値・ステップを出力用 Slot として投影しない。

title: 反復入口と range の Model 契約

level: MUST

## CST_005

`With` は少なくとも一つの順序付き `ContextEntry` と本体 `Block` を保持する。`ContextEntry` はコンテキスト式と任意の束縛先を保持する。Construct を保持できることは、指定した Target がその退出処理を実現できることを保証しない。

title: コンテキスト構造と実現可能性の分離

level: MUST

## CST_006

`Program` と他の Construct は `to_source()` / `to_c()` などの変換メソッドを提供しない。Model は Realization、Target Pack の import や生成処理への依存を持たず、変換入口は `pyinto.convert()` / `pyinto.realize()` に置く。

title: Model からの変換入口分離

level: MUST

## CST_007

基本 Construct の `parts()` は Realization 専用の `Name`、`TypeName`、`Joined`、`Requirements` を生成してはならない。変数名は Target 非依存の `Identifier`、型参照は `Symbol`、順序付き子要素は `tuple` を通じて公開する。出力専用の requirements は Program の Model 情報には含めない。

title: Model 部品と配置補助型の分離

level: MUST

## CST_008

`With` は順序付き ContextEntry を保持し、動的な名前付き子要素 `entry0`、`entry1` … として公開する。構文上の区切り文字や改行は Model に固定せず、Realization が決定する。

title: With の純粋な構造的展開

level: MUST

## CST_009

`For.parts()` が公開する要素は `entry` / `body` / 存在する場合の `otherwise` に限定する。対象言語に依存する `target/start/stop/step` の Slot 構成は Realization に委ね、非 `Range` 反復を持つ `For` も Model として保持できる。

title: For の反復形式非依存性

level: MUST

## CST_010

`Program` は元コードに存在する `body` だけを名前付き Model 要素として宣言する。出力用 `requirements` は Program の `parts()` や `HOLES` に含めず、Composition 側が出力 Slot として扱う。

title: Program の構造と出力要求の境界

level: MUST

## CST_011

`Literal` は Python 側の値として厳密な `int` または `str` のみ受け付ける。`bool`、浮動小数点、`None`、その他の型は Target Realization へ渡す前に構築時点で拒否する。整数の範囲制約や文字列の Target 表記は Realization が担当する。

title: Literal の Model 上の値域

level: MUST

## CST_012

`PythonFrontend` で生成した Construct Tree は Target Pack を選ばず参照可能であり、Python AST や生成専用 Layout 型を保持しない。複数の Target Realization を同じ Model に適用しても、元 Model は変更されない。これは Realization の利用規約であり、書換防止用の強制ラッパーを要求しない。

title: Model の単独利用と再利用

level: MUST

## CST_013

`Construct.HOLES`（旧称）は、そのクラスが静的に公開しうる Model 要素名の宣言であり、Template が必ず参照すべき Slot 一覧ではない。`parts()` は実際のインスタンスに存在する要素だけを返す。動的な番号付き要素は `accepts_part_name()` で宣言可能とし、実在しない要素への参照は合成時に拒否する。出力専用 Slot は Model の宣言には含めない。

title: Model 要素名と出力 Slot の区別

level: MUST

## CST_014

`Comparison` の演算子と被演算子の型、`Initialize` / `Assign` の型整合性、`Branch` / `While` の条件型は、Construct の生成時点で検証する。不正な Model は Realization 選択や `parts()` 呼び出しまで検証を先延ばしにせず、`ConstructError` で拒否する。妥当なインスタンスの `parts()` は構造の参照であり、Target 依存の判定を実行しない。

title: Model の構築時不変条件

level: MUST

## CST_015

整数式 `Arithmetic` は `+` / `-` / `*` / `//` / `%` および CST_065 のビット演算子と左右の整数 Value を順序付きで保持する。`IntegerUnary` は単項 `+` / `-` と CST_065 の `~`、整数 Value を保持する。演算子・型の不一致は Model 構築時に拒否する。値の事前計算や Target 固有の除算・剰余への書き換えは行わない。

title: 整数演算式の Target 非依存な保持

level: MUST

## CST_016

`BooleanOperation` は `and` / `or`、2個以上の Boolean Value の順序付き組を保持し、短絡評価を伴う操作として扱う。`BooleanNot` は Boolean Value を子として保持する。Model は実際の評価を行わず、Realization が評価順序と短絡性を実現する。両クラスは生成時に構造と型を検証する。

title: 論理演算式の順序と短絡性の保存

level: MUST

## CST_017

`FunctionSignature` は関数名、順序付きの型付き仮引数、明示的な戻り値アノテーションと単一の `return_type: ValueType` を保持する。戻り型の kind と複合型形状を別々の保存フィールドへ重複して持たない。`FunctionDefinition` はその署名と `Block` を保持し、所属する本体内の明示 `Return` の値と戻り型の整合性を構築時に検証する。`Branch`、ループ、`With`、`Try` の本体・handler・else・finally も確認するが、入れ子の `FunctionDefinition` と式内の `LambdaValue` の戻り値はそれぞれの定義に属するものとし、外側に混同しない。全経路の return 到達性は証明しない。各 `Parameter` は名前と型を Model 部品として公開し、`FunctionDefinition.parts()` は `return_type` を再帰的な `ValueType` のまま公開する。重複引数名、不正な署名や戻り型不整合は Model 構築時に拒否する。対象言語の呼出規約や型表記は決めない。

title: 関数の型付き署名と定義の構造

level: MUST

## CST_018

`Return` は省略可能な値式を保持し、`FunctionCall` は解決済み署名、順序付き実引数、戻り値種別を保持する。呼出の引数個数と型整合性は Model 構築時に検証する。`FunctionDefinition` は非 `None` 戻り型に値付き `Return` を要求し、通常の代入可能性（公称インスタンス型の継承を含む）で照合する。`None` 戻り型では裸の `Return()` と明示 `NoneLiteral` のみを許す。`Any` / `object` 戻り型には従来の広い値受理を維持するが、値のない Return は許さない。`None` 戻り値は明示的な `ValueKind.NONE` として区別し、評価、最適化、生成を行わない。

title: 戻り値と関数呼出の正規化

level: MUST

## CST_074

自作のトップレベル関数が持つ静的 `*args: T` は、既存の `FunctionSignature` の `variadic_parameter` に一つの `Symbol` として保存する。Symbolの役割は `ParameterRole.VARIADIC`、値型は `TupleType(variadic_element_type=T)` を持つ再帰的 `ValueType(TUPLE)` とし、固定長 `TupleType(element_types=(...))`、Listおよび要素一つのTと区別する。同種可変長タプルは0個以上の不変要素を保持し、型形状と `tuple[T, ...]` という型表記を提供する。対応する固定長Tuple値の全要素がTに代入可能なら、可変長Tuple変数への代入を許す。固定長Tupleの静的添字・アンパックに可変長Tupleを誤って使わない。`FunctionDefinition.parts()` は従来の `parameters` Slotに固定引数を保持し、可変長引数の存在時のみ `variadic_parameter` を別の名前付き `Parameter` として公開する。関数本体の同名参照は同一の可変長Tuple Symbolを指す。`FunctionCall` は固定引数を宣言順へ束縛し、余剰の位置引数を個々の `Value` として順序付きで後続保持し、型・個数・ソース評価順・省略既定値を検証する。Targetは呼出側の余剰値を、関数本体で単一の不変Tupleへ束縛する義務があるため、定義と直接呼出それぞれ `function.variadic.tuple_binding` / `call.variadic.tuple_binding` をAdmissionで要求する。Modelは特定TargetのABI・配列レイアウト・展開の実行方式を選ばない。現状の固定長 `CallableType` に自作可変長関数を誤投影せず、直接呼出のみ利用可能とする。

title: 自作関数の型付き可変長引数と実行時Tuple束縛

level: MUST

## CST_019

入れ子関数も既存の `FunctionDefinition` を `Block.children` 内へ再帰的に置いて表現する。新たな入れ子専用 Construct は導入しない。`FunctionSignature.scope` は関数宣言のレキシカルな所有経路、`Symbol.scope` は値宣言の所有経路を名前の組として保持し、同名の別束縛を区別する。`FunctionCall.signature` と `Reference.symbol` は解決済み宣言への参照を保持する。これらの属性は Target 名や捕捉変数の格納方式を規定しない。

title: 入れ子関数の再帰構造と束縛元の保持

level: MUST

## CST_020

`ValueKind.FUNCTION` は第一級関数値の種別であり、`CallableType` は位置引数の `ValueType` 列と戻り値の `ValueType` から成る Target 非依存の関数型である。`ValueType` は関数型について再帰的な `CallableType` を保持し、関数型以外への不正な付加および関数型の形状欠落を生成時に拒否する。関数型の整合性は型形状の厳密一致で判断し、Python の任意の Callable の部分型関係を推論しない。通常の `Value` は一つの `value_type` から `kind` および関数・タプル・リスト・辞書・インスタンスの型形状を読み取る。スカラー値だけは既存の値種別から `ValueType` を導出してよいが、構造型の値について型形状を独立した複数の規則として保持しない。マップ済みオブジェクトの参照には通常の `ValueType` を強要しない。関数値の宣言・代入・直接関数呼出の引数整合性は既存の `Initialize` / `Assign` / `FunctionCall` の契約を拡張して検証する。

title: 第一級関数値の構造型と型整合性

level: MUST

## CST_021

既存 `FunctionSignature` は宣言そのものの識別と直接呼出のために維持する。型情報が完全な署名は、同一宣言に安定して結び付く `value_symbol`（`ValueKind.FUNCTION` と対応する `CallableType` を持つ `Symbol`）を公開する。`Reference` は既存クラスのまま関数宣言や関数型変数を値として参照し、`FunctionCall` が関数型を返す場合は戻り値の `CallableType` を伝播する。入れ子関数、捕捉変数、関数値が生じる実行ごとの環境は、署名と既存のレキシカル参照構造から区別し、Runtime 上の関数値のインスタンス同一性や格納方式を Model は決めない。マップ済みの形状を持つ仮引数の関数署名は従来の直接呼出を維持し、関数値への変換だけを拒否する。戻り型には `ValueType` を要求し、未定義のマップ済みの戻り型を推測して構築しない。

title: 関数宣言と関数値の参照経路の分離

level: MUST

## CST_022

`FunctionValueCall` は静的な関数宣言に束縛された `FunctionCall` を変更せず、`ValueKind.FUNCTION` であり完全な `CallableType` を持つ任意の子 `Value` を呼出対象 `callee` として保持する。位置引数は順序付きで保存し、構築時に個数・明示型・ネストされた関数型形状を検証する。通常の値代入と同じ規則により、公称インスタンス型の引数では派生型から基底型への代入を認める。ネストした `CallableType`・`ListType`・`DictType`・`TupleType` の形状は従来どおり厳密一致とし、任意の構造的な型変性は推論しない。`parts()` は `callee` と存在する `arg0`、`arg1` ... を公開し、`accepts_part_name()` は動的な番号付き名称を受け付ける。関数値式の評価は一度だけ、実引数に先行し、実引数は記述順に評価するという契約を Realization に委ねる。呼出結果の `kind` と `callable_type` は callee の `CallableType.return_type` から伝播させる。関数オブジェクトの生成方式、捕捉変数の格納方式、Target の関数呼出規約は Model で決めない。

title: 第一級関数値を介する呼出の構造と型検証

level: MUST

## CST_023

クロージャーに必要な直接の静的依存は、既存 `FunctionDefinition` の本体と `Reference.symbol`、直接呼出の `FunctionCall.signature`、宣言の `scope` から読み出せる。`pyinto.analysis.lexical_captures(definition)` は当該関数本体が直接参照する厳密な外側の関数スコープの `Symbol` を初出順・宣言同一性付きで一度ずつ返す、Target 非依存・非変更の投影である。外側で宣言された入れ子関数の直接呼出や関数値参照も元の宣言 `value_symbol` を通して扱う。子の `FunctionDefinition` 本体は別の関数として扱い、この投影では再帰走査しない。モジュール階層の宣言、同じ関数の引数・ローカル名、自己再帰は捕捉に数えない。専用の Closure Construct は導入しない。

title: 既存宣言からの直接的なレキシカル捕捉導出

level: MUST

## CST_024

`Symbol` と `FunctionSignature` は静的な宣言を表し、関数の実行ごとに生成される値や環境そのものではない。したがって同一の入れ子関数宣言を共有する複数のファクトリ呼出でも、各呼出結果が必要な独立した環境を参照する意味契約は維持する。捕捉した可変束縛の参照・共有関係、外側の呼出が終了した後の参照の有効性、間接呼出時の環境の引き渡しを保証できるかは Realization が判定・実現する。`lexical_captures` は直接参照だけを返し、さらに内側の関数が持つ捕捉の推移的保持、関数値の逃避、寿命、アロケーションは推論しない。Realization が契約を実現できなければ明示的に拒否する。

title: 静的宣言と実行ごとのクロージャー環境の分離

level: MUST

## CST_025

`ValueKind.TUPLE` と `TupleType` は位置ごとの `ValueType` を順序付きの不変な型形状として保持し、`ValueType` / `Symbol` / 関数の署名・戻り値型に再帰的に組み込める。形状のないタプル型と、タプル以外に付いたタプル形状は構築時点で拒否する。`TupleValue` は評価前の Value 列を記述順に保持し、空タプルも許す。要素型・長さの違いは明示的な型不一致であり、Python の任意のタプル共変性・自動変換・実行を推論しない。初期化・代入・関数の受け渡しでは既存の型整合性判定を拡張し、同じ形状の値のみ受理する。

title: 固定長タプルの型形状と順序付き値

level: MUST

## CST_026

`TupleElement` はタプル型が確定した `Value` と 0 以上の静的な整数位置を保持し、モデル構築時に範囲内であることを検証する。`kind` および再帰的な `callable_type` / `tuple_type` は対応する要素の型情報から決まる。`parts()` は元の値式を `source`、添字を `index` として公開する。Realization は元の式を一度評価して該当する位置を取得する契約を担い、Target 固有のタプル表現を Model へ持ち込まない。可変長・動的添字・負の添字・代入先の添字操作は本段階では規定しない。

title: 固定位置のタプル要素参照と評価契約

level: MUST

## CST_027

`Raise` は対応する組込み例外クラスの静的な名前と、省略可能な文字列 `Value` のメッセージ式を保持する。現段階の例外クラスは `ValueError` / `TypeError` / `RuntimeError` に限定し、構築時に名前・型を検証する。メッセージの省略と指定は区別し、指定された式を Model 内では評価しない。`parts()` は `exception` に `Identifier`、指定時のみ `message` に元の `Value` を公開する。一般的な Python の例外インスタンス・任意のクラス生成・例外オブジェクトの属性操作を扱う型システムは導入しない。

title: 限定された組込み例外の送出構造

level: MUST

## CST_028

`ExceptHandler` は対象となる例外クラス名の非空で重複のない順序付き組とハンドラ本体 `Block` を保持する。`Try` は必須の本体 `Block`、順序付き `ExceptHandler` 列、任意の正常完了時 `else` と必ず終了処理を行う `finally` の `Block` を保持する。少なくとも一つの handler または `finally` を要求し、`else` は handler の存在を要求する。`parts()` は存在する `handlers` / `otherwise` / `final` のみを公開し、`variant()` は handler と finally の有無で選択する。

title: 例外処理の順序付き節と構築時不変条件

level: MUST

## CST_029

`Try` の handler は `try` 本体から送出された例外にのみ宣言順で適用し、最初に型が適合した handler を選ぶ。型に適合しない例外は伝播する。`else` は `try` 本体が例外も `return` / `break` / `continue` も伴わず通常完了した場合だけ実行する。`finally` は正常完了・例外・制御移行を含む退出経路で実行し、`finally` 自身の制御移行が先行する移行を上書きする Python の制御フロー契約を保持する。特定の Target における例外型一致、例外伝播、`finally` の実現は Realization が責任を持つ。必要な契約を満たせない Realization は生成を拒否する。既存の `With` の特殊メソッド・退出・例外抑制の契約は変更しない。

title: 例外伝播・else・finally の制御フロー契約

level: MUST

## CST_030

`ValueKind.LIST` / `ListType` は単一の再帰的な `ValueType` を要素型として保持し、リストの長さは型に固定しない。`ValueType` / `Symbol` / `FunctionSignature` / `CallableType` はこの要素型を関数・タプル内のネストも含めて伝播させる。`ListValue` は生成時の順序付き要素 Value 列を保持し、要素の同一構造型を検証する。空のリストも明示された要素型で構築できる。ソース上の別名束縛は既存 `Reference` による同一リスト値の共有を意味するため、Model は値を事前評価・複製しない。リストへの宣言・再代入・引数渡しは従来の型整合性検証を拡張して行い、Python の任意の共変性・自動変換を推論しない。リストの格納方式や実行時同一性の実現は Realization に委ねる。

title: 同種要素を持つ可変リストの構造型と値

level: MUST

## CST_031

`ListElement` はリスト型と判明した子 `Value`、整数型の添字 `Value` を保持し、要素の `kind` と再帰的な関数・タプル・リスト型情報を伝播する。`ListElementAssign` は既存リスト変数への `Reference`、添字 Value、型整合する右辺 Value を保持する独立した変更操作であり、変数自体の `Assign`（再束縛）とは区別する。両者は構築時にリスト・整数添字・要素型の契約を検証し、Model の式は評価しない。Realization はソースの評価順、各式の一回評価、負添字・範囲外の扱いを含む Python のリスト要素アクセス・更新の観測可能な意味、別名を介した変更の共有を実現するか、未対応として拒否する。モデル自体は実行時のリスト長・境界やメモリ配置を確定しない。

title: リスト要素参照・更新と可変参照の契約

level: MUST

## CST_032

`ValueKind.DICT` / `DictType(key_type, value_type)` は両方の再帰的 `ValueType` から成る可変辞書の構造型とし、キー型を厳密な `int` または `str` に限定し、値型は既存の明示的に許された `ValueType` とする。`ValueType`・`Symbol`・関数署名・`CallableType` は辞書形状を他の複合型内も含めて伝播させる。`DictValue` は `DictEntry(key, value)` を記述順に保持し、生成時のキー型・値型の整合を構築時に検証する。空の辞書値には型形状が必須である。辞書の各キー式と値式をその順に一度ずつ評価すること、等価キーの後続挿入は値を上書きし最初の挿入位置を保持すること、辞書値の別名は変更可能な同一オブジェクトを共有することを Model の意味契約とする。Python のハッシュテーブル実装や Target 上の格納方式は選ばない。

title: 型付き可変辞書の形状と順序付き生成

level: MUST

## CST_033

`DictElement(source, key)` は辞書 Value と型整合するキー Value の読み取りを保持し、値型の `kind` と再帰的な `callable_type`・`tuple_type`・`list_type`・`dict_type` を伝播させる。キーが存在しない読み取りは実行時の `KeyError` とする。`DictElementAssign(target, key, value)` は辞書変数への Reference と型整合するキー・値式を保持し、既存キーの更新または新規キーの追加を表す。更新時には既存のキー位置を変えず、新規キーは末尾へ挿入する。両操作は辞書値・キー型・値型を構築時に検証し、評価や格納は行わない。Target Realization は各子式の一回評価・順序、検索失敗、挿入順序、別名間の変更共有を保証するか、未対応として明示的に拒否する。`KeyError` が Model において汎用的な例外値・捕捉可能な例外型として導入されたわけではない。

title: 辞書要素の参照・追加・更新と失敗契約

level: MUST

## CST_034

`ValueKind.INSTANCE` と `InstanceType(name, scope)` は型の構造が等しくても異なる宣言のクラスを区別する公称型とする。`ValueType` / `Symbol` / `FunctionSignature` / `CallableType`、およびタプル・リスト・辞書の要素型はこの公称型情報を再帰的に保持する。`ClassSignature` は `InstanceType`、順序付きの `FieldDefinition`、`FunctionSignature` を保存し、型付き `__init__` を必須とする。`ClassDefinition` は既存の `FunctionDefinition` をメソッド本体として再利用し、宣言との一致を検証する。クラスオブジェクトの動的な Python メタ機構・Target での格納方式は Model に持ち込まない。

title: 公称インスタンス型と静的クラス宣言

level: MUST

## CST_035

通常インスタンスメソッドの受取手は `Symbol(role=ParameterRole.RECEIVER, kind=ValueKind.INSTANCE, instance_type=所属クラス)` として保持する。`FunctionSignature.receiver` が受取手の宣言を明示し、通常の `ParameterRole.ORDINARY` と区別する。`Reference` は同一の宣言 Symbol を参照し、`self` という名前そのものには特別な意味を持たせない。受取手であることは位置や名前から Realization が推測する情報ではなく Model が伝える情報である。受取手を Target 上で引数、オブジェクト、ポインタ等のいずれに表すかは Realization が決定する。

title: 明示的なメソッド受取手の意味契約

level: MUST

## CST_036

`InstanceCreation` は公称クラス、引数式、および新規インスタンス生成後に宣言済み `__init__` を実行する契約を保持する。生成ごとに独立したインスタンスが作られ、型付き参照の代入・再代入は同じインスタンスを共有する。`FieldInitialize` は初期化時の明示型付きフィールド確立、`FieldRead` / `FieldWrite` は確定済みフィールドとインスタンスを表す Value の関係を保持する。`MethodCall` は評価される受取手 Value、静的に確定したメソッド署名、明示実引数を分けて保存し、受取手を一度評価してから引数を記述順に評価する意味を持つ。型・メソッド・フィールドの整合性は Construct の構築時に検証する。インスタンスのメモリ寿命・属性格納・メソッド呼出 ABI・Target コード生成は Realization の責務とする。

title: インスタンス生成・属性・メソッド呼出の構造と契約

level: MUST

## CST_037

静的単一継承は、`InstanceType.base` と `ClassSignature.base` による宣言済み基底クラスへの直接参照として保存する。深さ N はこの再帰的な連鎖で表現し、深さごとの専用 Construct を設けない。派生クラスと基底クラスは異なる公称型であり、`InstanceType.is_subtype_of()` は宣言された祖先のみを辿る。インスタンス型の整合性は派生型から基底型への代入・引数・戻り値を許すが逆方向を推測しない。リスト・辞書・タプル・Callable の既存の形状一致を一般的な共変・反変に変更しない。継承されたフィールドとメソッドは `resolve_field()` / `resolve_method()` で定義元署名を取得し、派生定義へ内容をコピーしない。

title: 静的な単一継承と公称派生型の契約

level: MUST

## CST_038

`MethodCall` は既存の receiver・解決済みメソッド署名・引数・静的受取手クラスを保持したまま、`MethodDispatch.VIRTUAL` または `MethodDispatch.SUPER` と `lookup_start` を明示する。通常呼出は `VIRTUAL` であり、受取手の実行時の実クラスから静的に宣言された継承連鎖を辿って最も近いオーバーライドを選択する契約を持つ。Frontend は実行時のインスタンス型を断定しない。`SUPER` は現在のメソッドを定義するクラスの直上から静的に検索した署名へ直接到達し、Receiver は別インスタンスを生成せず現在の同一インスタンスを渡す。`__init__` の明示的な親初期化も後者に含む。Template/Slot やディスパッチ表の実装は Realization に委ねる。

title: 仮想呼出と super 呼出の明示的な区別

level: MUST

## CST_039

派生クラスはフィールドとメソッドの宣言を独立に持ち、基底の宣言済みフィールドを所有クラス情報付きで参照・更新できる。フィールドと継承メソッドの名前衝突は拒否する。`__init__` 以外のオーバーライドは明示位置引数・戻り値の型形状の一致を要求し、Python の任意の型分散を推論しない。`FieldRead`・`FieldWrite` および `MethodCall` は宣言所有者と受取手の派生型関係を検証する。Construct 上の参照共有と実行時の受取手クラス別ディスパッチは、Realization が実現すべき契約であって Model の実行ではない。クラスの Target Realization はこの段階では未登録。

title: 継承フィールド・オーバーライドの構造契約

level: MUST

## CST_040

静的な単一継承を持つインスタンスが、既存の `Reference`、関数の引数・戻り値、`TupleElement` / `ListElement` / `DictElement`、レキシカルな関数捕捉を経由しても、値の公称型と宣言元の関係を維持する。基底型の参照に派生インスタンスを格納しても、`MethodCall(VIRTUAL)` は実際の実行時クラスを静的に決めつけず、静的受取手型から解決した署名を保持する。フィールド変更は名前の再束縛と区別され、インスタンス参照の共有を Model の意味契約として残す。既存のタプル・リスト・辞書・Callable の形状一致を包括的な型分散へ変更しない。

title: 継承インスタンスと既存値構造の合成契約

level: MUST

## CST_041

関数型のインスタンスフィールドは、静的に宣言した `FieldRead` を関数値として参照でき、`FunctionValueCall(callee=FieldRead(...), arguments=...)` により既存の間接呼出契約を利用する。この呼出は、Receiver が暗黙に束縛される通常の `MethodCall` とは区別される。継承されたフィールドでも `FieldRead.owner` はフィールドの定義元を保持する。呼出対象式を一度評価し、位置引数を順に評価する契約は既存の `FunctionValueCall` と同じである。新しい Construct 種別やクラス実行時 ABI は導入しない。

title: 関数値フィールドと間接呼出の合成契約

level: MUST

## CST_042

`BooleanLiteral(value: bool)` は Python の `True` / `False` を、整数と区別した `ValueKind.BOOLEAN` の不変な定数 Value として保持する。Python の `bool` が `int` の派生型であることを利用して整数化せず、構築時に `type(value) is bool` を要求する。既存 `Literal` の厳密な整数・文字列値域、既存 Boolean 演算の短絡評価規則は変更しない。`variant()` は `true` / `false` を返し、対象 Target での表現は Realization が決める。

title: 整数と区別する Boolean 定数 Value

level: MUST

## CST_043

`NoneLiteral()` は Python の単一値 `None` を `ValueKind.NONE` の式 Value として保持し、`Return.value is None` など Model 上の省略値とは区別する。`NoneLiteral` は既存の `object` / `Any` と互換な値として初期化・再代入・関数引数・戻り値に渡せるが、`None` を一般的な変数型や `Optional` / `Union` として導入するものではない。既存の `-> None` 関数における `return None` と裸の `return` は従来の `Return()` に正規化する。`Literal` の旧値域と、コレクション要素の `None` 禁止は維持する。

title: None 値と省略の構造的な区別

level: MUST

## CST_044

`ConditionalExpression(condition, when_true, when_false, result_type)` は Boolean Value の条件と、互いに独立した真・偽の Value 式を順序付きの子構造として保持する。型付きの結果形状を `ValueType` として明示し、構築時に両分岐がこの型へ整合することを検証する。実行時には条件を一度評価した後、選択された枝だけを一度評価し、非選択枝を評価してはならない。枝式の副作用や例外を Frontend が事前に実行・選択せず、Target の分岐実現・値表現は Realization の責務とする。異なる型の枝を自動 Union 化する機能は追加しない。

title: 明示型付き条件式と非選択枝の非評価契約

level: MUST

## CST_045

`Length(operand)` は長さの取得を独立した整数型 Value として保持する。受理するオペランドは型が静的に確定した `str`、固定長 `tuple`、可変 `list`、可変 `dict` のみとし、`object` / `Any` や任意クラスの `__len__` を推論しない。オペランド式は利用時に一度だけ評価する。文字列の長さは Unicode コードポイント数、辞書の長さは重複のないキー数、リストの長さは利用時の要素数とする。タプルの型上の固定長だけで式の評価を省略してはならない。対象言語の格納方式と長さ取得手段は Realization が決める。

title: 型付きコンテナと文字列の長さ操作

level: MUST

## CST_046

`Absolute(operand)` は符号付き整数値の絶対値を表す整数型の Value であり、オペランドが `ValueKind.INTEGER` であることを構築時に検証する。オペランド式を一度だけ評価した数学的な絶対値を要求し、フロントエンドで事前計算しない。Target 整数型の範囲に伴う表現可否は Realization の責務である。浮動小数点、複素数、Boolean の整数扱い、ユーザー定義 `__abs__` は採用しない。

title: 整数絶対値の限定的な操作契約

level: MUST

## CST_047

`Extremum(operation, operands)` は `min` または `max` の操作種別と、2個以上の整数型 Value を順序付きで保持する。実行時にはオペランドを記述順に一度ずつ評価し、整数比較により最小値または最大値を返す。Iterable 1引数形式、`key=` / `default=`、任意型間比較、一般的な Python 特殊メソッド、キーワード・展開引数は対象外とする。Model は Target の整数範囲、比較関数、格納方式を決定しない。

title: 整数 min/max の順序付き多項操作契約

level: MUST

## CST_048

`IntegerSum(iterable, start=None)` は整数集約を、反復元の Value と省略可能な開始整数 Value から成る不変な整数 Value として保持する。反復元は厳密に型が確定した `list[int]`、全要素が `int` 型の固定長 `tuple`、または既存の整数 `Range` に限定する。空タプルと型付きの空リストは許す。`start` 省略時は整数ゼロを用い、指定時は整数 Value を要求する。反復元式を一度、明示 `start` 式を一度、その順に評価してから、要素を順に加算する契約である。Model は和を計算・定数畳み込みしない。任意の Iterable、文字列結合、真偽値の整数化、独自加算プロトコル、Target 固有の整数範囲は扱わず、実現方法と範囲制約は Realization に委ねる。

title: 明示型整数 sum の集約順序と開始値

level: MUST

## CST_049

`BooleanAggregate(operation, iterable)` は `any` / `all` と Boolean の `list[bool]` または全要素が Boolean 型の固定長 `tuple` の Value を保持する不変な Boolean Value である。反復元式を一度評価し、各要素を要素順に評価する。`any` は最初の真で評価を打ち切り、空なら偽を返す。`all` は最初の偽で打ち切り、空なら真を返す。Python の一般的な truthiness、任意 Iterable、特殊メソッドや非 Boolean 要素は採用しない。Model は短絡を実行せず、Realization が契約を満たすことを要求する。

title: 型付き any/all の順序付き短絡集約

level: MUST

## CST_050

`ValueKind.FLOAT` と `FloatingLiteral(value: float)` は既存の整数・文字列 `Literal` に変更を加えず、浮動小数点定数を独立した不変 Value として保持する。Python の有限な float 定数のみを受け入れ、`bool`・`int`・非有限値のリテラルは拒否する。`float` 型情報は型付き変数・関数・既存コレクションの型形状へ伝播する。特定のメモリ Interface や Target の表現方式を型情報から自動選択しない。

title: 既存整数型と独立した float 値と明示型

level: MUST

## CST_051

`FloatingArithmetic(left, operator, right)` は `+` / `-` / `*` / `/` を、`FloatingUnary(operator, operand)` は単項 `+` / `-` を、いずれも厳密な `ValueKind.FLOAT` オペランドに限定して保持する。値式・演算子・評価順序を保存し、Frontend では値を計算しない。演算の意味は Python の float の振る舞いに従い、丸めやゼロ除算等の結果に必要な意味を満たせない Realization は拒否する。整数除算や整数・float 混在式を既存の `Arithmetic` へ暗黙に取り込まない。

title: 型付き浮動小数点演算と既存整数演算の分離

level: MUST

## CST_052

`FloatingComparison(left, operator, right)` は厳密な float 同士の `<` / `<=` / `>` / `>=` / `==` / `!=` を Boolean Value として保持する。比較オペランドは一度ずつ左から評価し、NaN が演算結果として生じる場合の比較意味を維持する。暗黙の int/bool 変換、比較チェーンや浮動小数点の Target ABI は追加しない。

title: 浮動小数点の比較と型境界

level: MUST

## CST_053

`StringConcat(left, right)` は Unicode 文字列二つの連結、`StringRepeat(left, right)` は str/int または int/str の繰返しを表す不変 Value とする。子 Value はソース順に一度ずつ評価し、操作結果を Frontend では組み立てない。負の繰返し数は空文字列となるという Python の意味を要求する。既存の整数 `Arithmetic` の受理範囲は変更しない。

title: 文字列連結・整数回数の繰返し

level: MUST

## CST_054

`StringComparison` は str 同士の順序・等値比較6種を Unicode コードポイント列の辞書順として保持する。`StringContains(needle, haystack, negate)` は str 同士の部分文字列包含と否定を保持し、結果は Boolean Value とする。子式は記述順に一度ずつ評価し、Python の任意オブジェクトの特殊メソッドや非文字列との比較を暗黙に採用しない。

title: 文字列比較・部分文字列包含の静的契約

level: MUST

## CST_055

`StringElement(source, index)` は Unicode コードポイント列の整数添字参照を文字列 Value として保持する。負の添字は末尾から数え、範囲外では実行時に IndexError を発生させる。添字式を前倒し評価せず、スライス・代入・バイト添字・一般的な `__getitem__` は含めない。Target の Unicode 表現と正しい例外動作は Realization が担う。

title: 文字列の型付き単一要素参照

level: MUST

## CST_056

既存 `FunctionCall` / `MethodCall` / `InstanceCreation` は、型・個数を検証済みの `arguments` を仮引数の宣言順に保持し、新規 `evaluation_order` に実引数がソース上で評価される順序（仮引数の添字の順列）を保持する。省略時は従来の `(0, 1, ...)` と同じ。`argument_evaluation_order` と `evaluation_arguments` は、Realization が実際の式評価順を読み取れる非変更の導出であり、構築時に欠損・重複・不正な添字を拒否する。評価順と引数束縛順は独立した契約であり、特に Target の引数評価順が未規定のときは Realization が一回評価と順序保存を担う。既存の `arg0` 等の子 Slot の宣言順と直接呼出の型契約は維持する。関数値の間接呼出に引数名を推論して付加しない。

title: 静的キーワード引数の束縛順と式評価順の分離

level: MUST

## CST_057

`FunctionSignature.parameter_defaults` は、仮引数ごとに `Value | None` の整列した不変値を保持する。Python の `None` 値は `NoneLiteral()`、デフォルト指定の不在は `None` として明示的に区別する。受理するデフォルトは整数・有限浮動小数点・文字列・Boolean・None の型整合したリテラルに限り、受け取り手や必須引数より前に置かれた無効なデフォルト、可変値や任意の式は拒否する。`FunctionDefinition.parts()` の `Parameter` は、存在する場合だけ `default` を子要素として公開する。既存の `FunctionCall`、`MethodCall`、`InstanceCreation` の引数 Slot は省略値で補完されて宣言順に並ぶが、新しい `omitted_arguments` は実際に指定されなかった仮引数の位置を保持し、`supplied_evaluation_arguments` はソースに書かれた実引数式だけを記述順で公開する。仮想ディスパッチされるオーバーライドは省略位置とデフォルト値を基底メソッドと一致させる必要がある。補完値は不変のリテラルであり、Python の一般的な関数定義時評価や可変オブジェクトの共有を要求しない。Model は Target 実現を行わない。

title: 静的スカラーデフォルトと省略引数の独立した契約

level: MUST

## CST_058

`MethodKind.STATIC` はクラス所属だが Receiver を持たない関数宣言を表す。既存 `FunctionDefinition` / `FunctionSignature` / `Parameter` を利用し、`ClassMethodCall` にクラス由来の `ClassReference` と呼出引数を保持する。型付き引数・限定されたデフォルト値・明示引数の評価順を検証し、インスタンスの Receiver と同一視しない。実行時の Python descriptor オブジェクトは生成しない。

title: 静的メソッドと明示的なクラス所属

level: MUST

## CST_059

`MethodKind.CLASS` は `ParameterRole.CLASS_RECEIVER` の仮引数を最初に持つ。通常の `RECEIVER` と区別し、名前 `cls` への依存はない。`ClassMethodCall.class_source` は呼出元のクラスを静的に指定する `ClassReference` または型付きクラス Receiver の `Reference` を保持する。継承先からの呼出では実行時のクラス同一性を継承先として引き渡す。`ClassReceiverCreation` は同じ実行時クラスのインスタンスを生成する契約とし、宣言元クラスへの固定生成へ書き換えない。`ClassMethodCall` と `ClassReceiverCreation` は引数名の束縛・式評価順・省略引数を保持し、対応できない Realization は拒否する。

title: クラスメソッドと実行時クラス Receiver の保持

level: MUST

## CST_060

限定された `@dataclass` は、静的フィールド宣言から既存 `ClassSignature` / `FieldDefinition` と、合成した `FunctionSignature(__init__)` / `FunctionDefinition` / `FieldInitialize` を得る正規化規則である。専用の汎用 Decorator Construct は導入しない。型付きフィールドの宣言順、静的なスカラーデフォルト、省略・キーワード指定による生成を既存契約に従い扱う。Python の dataclasses が一般に生成する `__repr__` / `__eq__` / `__hash__`、`__post_init__`、`default_factory`、frozen、slots、一般的な継承とクラス書換えは契約に含めない。

title: 縮小 dataclass 契約の既存 Construct への正規化

level: MUST

## CST_061

匿名関数は専用のクロージャー/関数定義体系ではなく、式としての `LambdaValue` に内包した既存の `FunctionDefinition` / `FunctionSignature` / `Parameter` / `Block` / `Return` で保持する。`LambdaValue` は関数型の `Value` であり、型付き仮引数、単一の戻り値式、レキシカルな束縛関係と式が評価される位置を保持する。ラムダ生成式の評価による関数値は呼出回ごとに必要な外側のレキシカル環境を参照し、環境の確保・共有・寿命は Realization に委ねる。`LambdaValue.parts()` は `definition` を子として公開し、静的捕捉は既存の `lexical_captures(definition)` から導出可能とする。合成時に任意の Python 関数オブジェクトの動的な意味論を推論しない。`FunctionCall`、`FunctionValueCall`、既存 `FunctionDefinition` の意味を変更しない。

title: 式としての型付き匿名関数とレキシカル環境

level: MUST

## CST_062

`Pass` は実行時の効果を持たない明示的な文を表す Construct とする。`parts()` は空で、Target の出力記法は規定しない。`Program`、`FunctionDefinition`、`ClassDefinition` の `docstring: str | None` は、先頭に置かれた文字列リテラルに由来する静的な宣言文書を元の文字列として保持する。空文字列と文書の不在は区別する。docstring は実行される子 Construct や出力 Slot とせず、Python の一般的な `__doc__` 属性、内省、実行時文字列式の意味を Model に追加しない。既存の型・呼出・クラス契約は変更しない。Realization に文書の出力を強制せず、要求される場合は Target 側で扱う。

title: 無操作文と宣言docstringの静的保持

level: MUST

## CST_063

`AugAssign(target, operator, value, mode)` は、既存の型付き格納先に対する複合代入を、単純代入と算術式への事前展開なしに保持する。初期契約では `target` は `Reference` または `FieldRead` に限り、厳密な整数同士の `+` / `-` / `*` / `//` / `%` と、厳密な浮動小数点同士の `+` / `-` / `*` / `/` のみを受理する。`mode=AugAssignMode.REBIND` は読み取ったスカラー値から新しい値を計算して同じ束縛先を更新する操作を表し、`IN_PLACE` 等のオブジェクト破壊的更新は受理しない。格納先の決定（フィールド Receiver を含む）と現在値の読取は一度だけ、右辺の評価はその後に一度だけ実行し、適用される整数・浮動演算の意味は既存の `Arithmetic` / `FloatingArithmetic` に従う。Model はTarget上の一時変数・フィールド更新記法を決定せず、必要な評価・再束縛契約をConstruct提供者のAdmissionRuleとして登録する。

title: 型付きスカラー複合代入と格納先一回評価

level: MUST

## CST_064

`ComparisonChain(operands, operators)` は3個以上の順序付き Value と隣接する比較演算子を保持するBoolean Valueとする。各演算子は `<` / `<=` / `>` / `>=` / `==` / `!=` に限定し、全オペランドは `int`、`float`、`str` のいずれか同一の明示型を要求する。実行時には左から右へ必要になった式だけを一度ずつ評価し、隣接比較の中間値は再評価せず再利用する。途中の比較が偽ならその時点で終了し、残りの式は評価しない。二項Comparisonの複製やBooleanOperationへの無条件分解はこの契約を損なうため、Frontend/Modelでは行わない。Modelは対象言語の比較演算の実行順・一時変数の配置を決定せず、Realizationは比較の順序・中間値の一回評価・短絡を満たせない場合に拒否する。

title: 型付き比較チェーンと短絡・中間値一回評価

level: MUST

## CST_065

`IntegerTrueDivision(left, right)` は厳密な `int` 型の左右オペランドを順序付きで保持し、結果を `float` とする独立した値Constructである。整数の切り捨て除算や `FloatingArithmetic` への暗黙変換は行わない。ゼロ除算・非常に大きな整数のfloat変換時の例外を含め、Pythonの数値的な真の除算の意味を契約とし、FrontendもModelも値を計算しない。`Arithmetic` は `&` / `|` / `^` / `<<` / `>>` を追加し、`IntegerUnary` は `~` を追加する。いずれも厳密な整数型であり、負の整数や任意精度の整数に対してPython式の無限符号拡張のビット意味を持つ。シフトの負の回数は実行時エラーとし、事前に式を評価して受理可否を決めない。左右のオペランドの順序付き一回評価を保持し、ビット演算・シフト回数・真の除算の追加契約をConstruct提供者のAdmissionRuleで要求する。`AugAssign`の整数演算子にも同じビット演算を追加するが、既存の格納先一回評価とスカラー再束縛を維持する。Realizationの支持宣言は意味保存を証明せず、Target固有の整数幅や算術規則をModelへ導入しない。

title: 型付き整数ビット演算と整数同士の真の除算

level: MUST

## CST_066

`IntrinsicDefinition` は Target 非依存の型付き基本操作の提供者宣言であり、識別名、任意の Receiver の `ValueType`、固定長の位置引数型列、戻り値 `ValueType`、追加の具体的な意味契約キーを保持する。`IntrinsicCall` はその不変定義、任意のReceiver式、実引数式の順序付き列を参照し、正規化時の型・個数の照合を行う。Receiverは存在するとき最初に1回、引数は元の順にそれぞれ1回評価する意味を持つ。操作自体の意味、変更・例外等は提供者が明示する契約であり、Modelが呼出を実行したりTarget固有のABI・文字列表現を選んだりしない。`variant()` は `intrinsic.<受け手種別またはglobal>.<名前>` を返し、`parts()` は存在する `receiver` と `arg0`…を公開する。`IntrinsicRegistry` の型付き複数シグネチャと限定的な型変数は CST_067 に従う。実行時属性検索・Targetの暗黙の実装選択は導入しない。`AdmissionRule` は操作キーと追加の意味契約に加え、Receiverの一回評価、Receiverから引数への先行、各引数の一回評価、複数引数の評価順を必須条件として導出する。Target の対応宣言は意味保存の証明ではない。

title: 型付き基本操作の提供者定義とIntrinsicCall

level: MUST

## CST_067

`IntrinsicDefinition.key` は操作の系列（`intrinsic.global.str` / `intrinsic.list.append` 等）を表し、型ごとに分割しない。`IntrinsicRegistry` は同じ操作キーの下に、Receiverと位置引数の静的シグネチャが異なる複数の定義を登録できるが、同一シグネチャの重複・異なる戻り値や契約による上書きを拒否する。静的な既知型と引数個数だけで照合し、該当候補なし・複数候補への適合は拒否する。暗黙変換、候補順位付け、動的ディスパッチ、実行結果に基づく推論を行わない。`IntrinsicTypeVar` と `IntrinsicListType` は提供者定義の署名内だけの静的な型パターンであり、`list[T].append(T)` 等の既知Receiver要素型と引数型の一致を束縛する。戻り値の型変数は入力から束縛可能でなければ宣言時に拒否する。`IntrinsicCall` には解決済みの具体的な `IntrinsicDefinition` を保持し、実行時の型変数・汎用型推論を持ち込まない。同じキーでも署名ごとの `obligations` は区別され、Realizationは共通操作キーと選択済み署名の意味契約に対応できなければ拒否する。対応宣言はTarget上の意味保存の証明ではない。

title: 基本操作の複数静的シグネチャと署名内限定型変数

level: MUST

## CST_068

標準提供者表 `standard_intrinsics()` は `str` / `int` / `float` の引数なしと厳密な `int` / `float` / `str` / `bool` の1引数型変換、および `str.upper()` / `str.lower()` を、固定した静的署名と署名固有の具体的な意味契約として宣言する。Pythonにおける10進整数の文字列表現、floatの `str` 表現（`1.0` と `-0.0`、非有限値を含む）、真偽値の `True` / `False` 表現、文字列からの数値変換における構文と例外、floatからintへの0方向の切捨て・非有限値例外、任意精度整数からfloatへの範囲超過、Unicode大文字・小文字変換（文字数が変化し得る）を、それぞれ該当する署名の実行時意味とする。引数がない場合は `str()` は空文字、`int()` は0、`float()` は0.0とする。引数の実行結果に基づく定数畳み込み・暗黙の型昇格はしない。`str(list)`、`int(str, base)`、任意の動的 `__str__` / `__int__` / `__float__`、一般のオブジェクト文字列化やformatは採用しない。Realizationは共通系列キーと署名固有の契約の両方に対応しなければならず、Target固有の出力アルゴリズムはModelで定めない。

title: 型付き標準変換とUnicode文字列メソッドの意味契約

level: MUST

## CST_069

`FormattedString(fragments)` は、型が文字列のValueを1個以上保持し、左から右へ各fragmentを一度だけ評価してUnicode文字列として連結する。Pythonのf-string内の各式はFRT_066に従って型付き `str(x)` の `IntrinsicCall` とし、従来のCST_068の型別文字列表現の意味契約を再利用する。書式指定、`!r` / `!a`、任意のユーザー定義 `__format__` は含めない。ModelはTargetの文字列結合方式を指定しない。`PrintValues(values)` は0個以上の文字列Valueからなり、すべての引数式を出力開始前にソース順で一度ずつ評価し、空白区切りと末尾改行で標準出力する意味を保持する。値の文字列化は個別の型付きIntrinsicCallで表し、出力・評価順序の契約とは区別する。従来の `Call(print, (str,))` は標準Target Packの既存レシピのため維持する。Realizationは新しいConstructへ対応がなければ拒否する。

title: 書式なしf-stringと複数値出力の意味契約

level: MUST

## CST_071

`Membership(element, container, negate)` は左の対象値と右の型付き
`list[T]` または `dict[K,V]` を順序付きのValueとして保持し、Booleanを
返す。左を先、右を後にそれぞれ一度だけ評価して所属判定し、`negate`が
真ならその結果を反転する。Listでは先頭から各要素の同一性または
Python等値規則で探索する。Dictではキーのハッシュ・等値の意味を使い、
値の所属判定はしない。`element`の既知のValueTypeはListの要素型、
またはDictのキー型に代入可能であることを要求する。
右辺がStringなら既存の `StringContains` のUnicode部分文字列意味を使用し、その意味のAdmissionも別途要求する。
その他の型や任意のPython `__contains__` は対象外とする。
入力の実行・値探索・Target固有のストレージ/ハッシュ方式の選択は
Modelで行わず、型別の `membership.*` 契約をAdmissionで要求する。

title: 型付きList・Dict所属判定の意味契約

level: MUST

## CST_070

`UnpackAssign(targets, value)` は既宣言の通常型付き Reference の固定長列と、同じ要素数を持つ型付き Tuple Value を保持する。各位置の型の代入可能性を Model 構築時に検証し、長さや型の不一致、マップ済みオブジェクトの再束縛、Receiverの再束縛を拒否する。実行時には右辺全体を一度だけ評価して各位置の値をすべて確定させ、その後左から右の順で対象へ代入する。重複した対象名は許可し、後に代入した値が残る。`a, b = b, a` を独立した Assign 列に脱糖せず、Target固有の一時変数配置も決めない。Realizationは RHS 保存と代入順序の契約を満たせなければ拒否する。

title: 固定長Tupleの一括アンパック代入

level: MUST

## CST_072

`SliceValue(source, start, stop, step)` は既知の型付きListまたはStringを対象に、開始・終了・ステップそれぞれの式と省略（`None`）を区別して保持する。対象を最初に、存在する境界式を start → stop → step の順で一度ずつ評価し、Python型の負添字・範囲外の切詰め・負ステップと省略境界の相互作用を実行時の契約とする。ステップが実行時に0なら `ValueError` が発生し、Modelの構築時に値を実行しない。結果型はListなら同じ要素型の新しい外側List、StringならUnicodeコードポイントで選ばれたStringである。Listの要素参照は共有され得るため、深いコピーは約束しない。ModelはTarget固有の添字計算やメモリ配置を決めない。辞書・Tuple・任意の `__getitem__` は対象外とする。Realizationは順序・Python式の添字調整・型別のコピーまたはUnicode意味を明示的に支持しなければならない。

title: 型付きシーケンススライスの省略境界と浅いコピー

level: MUST

## CST_073

`IterationEntry(target, iterable, introduces_binding)` は反復入口で更新する一つの型付き Symbol の `Reference` と反復元 Value を保持する。`introduces_binding=False` は既存の型付き束縛の反復更新、`True` は反復入口での新規束縛導入を示す。いずれも各反復で同じ Symbol を更新し、反復ごとの別 Symbol は生成しない。空の反復元では導入変数が一度も束縛されない可能性があり、Modelは架空の初期値や `Initialize` を挿入しない。導入フラグはTarget固有の変数宣言の配置を決定せず、`parts()` は従来の `target` と `iterable` だけを公開する。導入形を実現するには、Construct提供側の `iteration.binding.introduced` 契約への支持が別途必要であり、従来の反復形式・break/continue・正常終了elseの義務も残る。既存の型付き反復入口は同じ既定のFalseで表現できる。

title: 反復入口における既存束縛と新規束縛の区別

level: MUST

## CST_076

`ValueType.label` は `pyinto.kinds` の語を表す `KindLabel(name, arguments)` を保持できる。`name` は語、`arguments` は正の整数または `ValueType` の列であり、ソースの記述をそのまま記録する。Host はラベルの意味（サイズ、範囲、表現、実行時の振る舞い）を定義せず、検査もしない。ラベルは `ValueType` の等価比較とハッシュに参加せず、型の互換は Python 側の種別と構造だけで決まる。唯一の追加規則として、`Void` / `Nil` / `Null` のラベルを持つ `None` 型の値は、ラベルを持つ宣言型へ代入・束縛できる。`annotation()` はラベルがあればその綴り（例: `Pointer[Int[32]]`）を返す。

title: 意味を持たないKindラベルの保持

level: MUST

## CST_077

値・比較・ポインタ操作に関わる Kind の語は次の Construct として Model に記録する。`NoneAlias(name)` は `Void` / `Nil` / `Null` の値であり、variant はそれぞれ `void` / `nil` / `null` とする。`NoneAliasComparison(left, operator, right)` は一方が None 別名で他方がラベルを持つ値である `==` / `!=` 比較とする。`AddressOf(target)` は型付き変数の `Reference` から `Pointer[変数の型]` のラベルを持つ値を作り、`PointerLoad(pointer)` は `Pointer[T]` のラベルを持つ値から `T` 型の値を作り、`PointerStore(pointer, value)` は `Pointer[T]` へ `T` に代入可能な値を書き込む文とする。これらは実行上の意味を持たず、Admission の意味義務も持たない。どう実現するかは Target が決める。

title: Kindの値・比較・ポインタ操作のConstruct

level: MUST

## CST_078

`ClassDefinition.labels` はクラスに付けられた `@Interface` / `@MixIn` / `@Implements(...)` を、ソース上の記述順に `KindLabel` として保持する。`Implements` の引数は実装先クラスの `InstanceType` を持つ `ValueType` の列とする。同じ語彙の重複は拒否する。ラベルは継承関係・メソッド集合・インスタンス化の可否を変えず、Target へ情報として渡すだけである。

title: クラスに付けたKindの記録

level: MUST

## CST_079

動的メモリの語彙は、形と所有を型のラベルで表す。`Buffer[T]` は実行時に長さが決まる `T` の列で、Python 側では `list[T]` の形を持つ。`Owned[X]` と `Shared[X]` は `X` の Python 側の形を保ったまま所有のラベルを付け、`X` には単体の型も `Buffer[T]` も書ける。ラベルのない `Buffer[T]` は所有しない列を表す。Host はこれらの意味（確保の方法、寿命、共有の仕組み）を定義しない。

title: 動的メモリの形と所有のラベル

level: MUST

## CST_080

動的メモリの操作は次の Construct として記録する。`MemoryNew(element_type, value)` は `Owned[T]`、`MemoryNewBuffer(element_type, length, value)` は `Owned[Buffer[T]]` の値を作る。`MemoryRelease(handle)` は `Owned` / `Shared` の値の寿命の終わりを表す文、`MemoryResize(target, length)` は所有する `Buffer` の変数の長さを変える文、`MemoryLength(handle)` は `Buffer` の長さ、`MemoryBorrow(handle)` は単体なら `Pointer[T]`、列ならラベルのない `Buffer[T]` を返す所有しない参照、`MemoryCopy(destination, source)` と `MemoryFill(handle, value)` は `Buffer` どうしの複写と全要素の設定を表す文とする。`MemoryRelease` と `MemoryBorrow` は対象の型から `single` / `buffer` の variant を持つ。いずれも実行上の意味と Admission の意味義務を持たず、どう実現するかは Target が型のラベルを見て決める。

title: 動的メモリの操作のConstruct

level: MUST

## CST_081

`pyinto.kinds.datatypes.general` の `Wide[X]` / `Narrow[X]` は `int` / `float` を基準にした相対的な大小を表し、入れ子の深さが段階になる。`Unsigned[X]` は整数の符号なしを表し、常に最も外側に書く。`Size` / `Index` / `Byte` は整数の役割を表す。いずれも Python 側の形は基準の型のままとし、Host は実際の大きさや表現を定義しない。同じ意味に複数の綴りが生じないよう、`Wide` と `Narrow` の混在、`Unsigned` を内側に置く書き方、整数以外への `Unsigned`、基準の型以外への `Wide` / `Narrow` を拒否する。

title: 汎用のdatatypes：相対的な大小・符号・役割

level: MUST
