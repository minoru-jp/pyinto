<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/specification/frontend.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# Python Frontend

一般の Python 実行や自動型推論を約束しない。

## FRT_001

`PythonFrontend.parse(source)` は入力テキストを Python AST で解析し、`Program` とその Construct 子構造へ正規化する。元の Python プログラムやマップ先のメソッドを実行しない。受理できない構文・未解決の参照は推測で補わず拒否する。

title: AST からの静的な正規化

level: MUST

related: [CST_001](construct.md#cst_001)

## FRT_002

新しい変数は原則として型アノテーションを伴う値付きの宣言でなければならない。ただし、FRT_070 の `for` 反復入口における既知要素型からの導入だけは例外とする。既存名への単純な再代入は型を再宣言せずに許容するが、既知の型との不整合は拒否する。通常型は現状 `int` / `str` / `bool` / `float` / `object`、明示 import された `typing.Any`、登録済みのマップ済みクラスに限定される。通常の型注釈は表記と一つの `ValueType` に正規化し、マップ済みクラスの注釈はマップ済みオブジェクトの宣言として別に扱う。型を7項目へ分解する中間表現は用いない。

title: 明示的な型付き束縛

level: MUST

related: [CST_002](construct.md#cst_002)

## FRT_003

`if` / `while` / `for` / `with` の本体および各 `else` 節の型付き新規束縛は FRT_071 の限定規則に従う。これらのブロックにおけるマップ済みオブジェクトの宣言・再束縛は拒否する。`try` 系の各節での新規宣言もFRT_021の制限を維持する。`for` の単一ループ変数の導入はFRT_070の限定規則に従い、`with ... as` の束縛先は使用前に型付きで宣言されていなければならない。`for` の反復元は整数 `range`、文字列、`list[T]`、固定長 `tuple` に限定し、反復要素の既知の型がすべて対象変数へ代入可能な場合だけ受理する（空タプルは要素型の検査を要しない）。型の不明な一般 Iterable、辞書、非反復可能な値は拒否する。`break` / `continue` は少なくとも一つの外側ループを必要とする。

title: 制御構造内の名前束縛の制限

level: MUST

related: [CST_003](construct.md#cst_003), [CST_005](construct.md#cst_005)

## FRT_004

`range()` は1〜3個の位置引数に限定し、各引数は既知の整数 Value として正規化する。従来の単一比較・整数比較に加え、FRT_061 で明示的に採用した比較チェーンはその限定契約に従う。FRT_007〜008 / FRT_060〜061 に定める以外の演算式、暗黙の変数定義、未対応文を自動補完しない。

title: 現在の式サブセット

level: MUST

related: [CST_004](construct.md#cst_004)

## FRT_005

Python側のInterface Mappingは、`InterfaceMappingRegistry`に完全修飾名で明示登録された関数・クラスだけを認識する。先頭の連続するimport節では`from module import function [as alias]`に加え、`import module[.submodule] [as alias]`、`from package import submodule [as alias]`を受理する。絶対importだけを対象とし、完全修飾したMapping登録と一致するモジュール経由の関数呼出だけを解決する。標準ライブラリか独自ライブラリかでは区別しない。単に親パッケージをimportしただけでは未importの兄弟サブモジュールへの参照を許可しない。未登録のモジュール・関数・属性、スコープ衝突、動的参照は拒否する。import対象を実際にPythonで読み込んだり実行したりしない。外部関数Mappingは従来の位置引数型列に加え、`InterfaceParameter`による名前付きパラメータ・型・末尾の不変Modelリテラル既定値を明示登録できる。名前付き署名ではPythonの位置引数とキーワード引数を宣言順へ束縛し、余剰・不明・重複・型不一致・必須引数不足を拒否する。省略分は登録済みの既定値で補完し、Pythonソース中の引数式を実行しない。副作用のある式をキーワードの並び替えで再順序化する場合は、任意の外部Constructに汎用的な評価順序表現がないため拒否する。`InterfaceVariadicParameter`により同種の型で静的に個数が確定する可変長位置引数を宣言できる。Python式を再評価せずに順序付きの引数列としてfactoryへ渡し、動的な引数展開は拒否する。同一完全修飾関数名に異なる複数署名を明示登録でき、名前・個数・型・既定値を照合して候補が一つに確定した場合だけそのfactoryを呼ぶ。重複した署名は登録時、候補なし・複数候補は解析時に拒否し、登録順を優先順位にしない。引数式は署名候補数に関係なく一度だけ正規化する。展開引数・キーワード専用引数・動的なデフォルトは対象外である。従来の位置引数型列によるMappingは同じ受理条件で保持する。`@maps(function)` を親クラス、入れ子の `@signature(...)` とクラス属性 `factory = ...` を個別の関数署名とし、`InterfaceMappingRegistry.from_declarations()` から従来と同じ `InterfaceFunctionMapping` へ明示的に変換できる。`@maps` は宣言時に参照したトップレベル関数の定義元 `__module__` と `__qualname__` を完全修飾識別名として使う。宣言の自動登録はせず、再エクスポート先の公開名、任意Callableやクラス/メソッドMappingの親子宣言、ソース解析時のPython関数実行は行わない。関数Mappingの特別な `_force` キーワードは副作用のない定数値に限定して正規化時に取り除く。

title: 明示登録された外部API Mappingのみ解決

level: MUST

## FRT_006

一つの `PythonFrontend` インスタンスを繰り返し使用しても、前回の parse で得た変数宣言、関数・モジュールimport別名、ループ深さ、マップ済みオブジェクト参照を次の parse に持ち越してはならない。

title: 解析単位間の状態分離

level: MUST

## FRT_007

Python AST の `+` / `-` / `*` / `//` / `%` の2項演算と整数の単項 `+` / `-` は、明示的に整数である Value の演算として正規化する。定数単項符号は従来どおり `Literal` にしてよい。整数同士の `/` とビット演算は FRT_062 に従う。`**` や宣言型のない演算は推論で補わず拒否する。新たな変数への代入は従来どおり型宣言を要求する。

title: 整数算術式の AST 正規化

level: MUST

related: [CST_015](construct.md#cst_015)

## FRT_008

`and` / `or` は Python AST のオペランドの順序とネストを保持して `BooleanOperation` にし、`not` は `BooleanNot` にする。現段階でサポートするのは型が Boolean と判明しているオペランドのみとし、Python の一般的な truthiness 解析や短絡評価の事前実行は行わない。

title: 論理演算式の AST 正規化

level: MUST

related: [CST_016](construct.md#cst_016)

## FRT_009

トップレベルの `def` について、全引数と戻り値の単純な型アノテーションを要求する。引数・ローカル変数の独立したスコープを作り、関数内の `return` を `Return` に正規化する。戻り値型の整合性は Model と同じ代入可能性規則で検証してソース位置付きで診断し、Model 側でも関数定義の構築時に明示 `Return` の型を検証する。戻り値の全経路到達性は推論しない。`return` が関数外に現れたら拒否する。

title: 型付き関数定義とローカルスコープ

level: MUST

related: [CST_017](construct.md#cst_017), [CST_018](construct.md#cst_018)

## FRT_010

入力モジュールのトップレベル関数署名は本体の正規化前に収集し、前方参照・再帰呼出の構造的解決を許可する。関数呼出は署名に照らして位置引数の個数と型を確認する。FRT_058 で識別・正規化ハンドラーを明示登録した宣言以外のデコレータ、FRT_050〜051 の範囲外の既定引数、可変長引数、FRT_048 で定めた範囲外の keyword 引数、FRT_011 の範囲外の入れ子定義、非対応の型と束縛は推測で補わず拒否する。これらの新しい Model に対する Target Realization は本段階では追加しない。

title: 関数導線の決定論的な解決と受理範囲

level: MUST

related: [CST_017](construct.md#cst_017), [CST_018](construct.md#cst_018)

## FRT_011

型付き関数の本体に直接置かれた型付き `def` は、既存の `FunctionDefinition` と `Block` の再帰構造として正規化する。各関数本体の直下で定義された署名を先行収集し、その関数の直上からモジュールまで順にたどる静的レキシカル解決によって、外側の型付き値への読み取り参照、名前による直接呼出、再帰・同階層の前方参照を解決する。`Reference.symbol` と `FunctionCall.signature` は解決先の同一宣言を保持し、同名の別スコープは所有経路で区別する。深さに応じた個別 Construct は定義しない。

title: 関数の階層的な名前解決と再帰構造の正規化

level: MUST

related: [CST_017](construct.md#cst_017), [CST_019](construct.md#cst_019)

## FRT_012

内側の関数が外側の変数を読むために、関数を値として返すことや Python の動的なクロージャー実装を要求しない。現在は外側の変数への再代入を行う `nonlocal`、FRT_072 の限定範囲を超える `global`、FRT_013 に規定する範囲を超えた関数値の操作、関数の制御構造内部での定義を受理しない。各スコープのローカル名は内側の関数定義内を走査せずに予約し、宣言以前の使用や外側の同名宣言への誤解決を防ぐ。定義済みの親スコープの名前が内側へ自動的に書き込み可能になるわけではない。新規 Realization はこの段階では追加しない。

title: スコープ解決の明示的な制限と未実装事項

level: MUST

related: [CST_019](construct.md#cst_019)

## FRT_013

先頭 import 節で明示的に import した `typing.Callable`（別名可）について、位置引数型を列挙する `Callable[[...], ...]`（空引数リストおよびネストも可）を関数・引数・型付き変数のアノテーションとして正規化する。関数名を値として参照した場合、当該署名の `value_symbol` への `Reference` を生成する。`Callable` 型変数への初期化・再代入、関数値を直接呼出の引数として渡す操作、関数型を返す `return`、関数型の戻り値を持つ直接 `FunctionCall` は、静的な関数型の一致を検証したうえで受理する。外側の変数を読む入れ子関数の参照構造は既存のスコープ構造を利用し、特別な Closure Construct は定義しない。

title: 明示的な Callable 型と関数値参照の正規化

level: MUST

related: [CST_020](construct.md#cst_020), [CST_021](construct.md#cst_021)

## FRT_014

第一級関数値を参照・型付きで受け渡すことと、当該値を呼び出すことは異なる契約とする。関数値を介する間接呼出は FRT_015〜016 で別途規定し、第10段階までの未対応制限をそこで解除する。Callable の `...`、型推論、未登録型、マップ済みの形状を含む Callable、`nonlocal` による再束縛、動的な関数属性操作などは引き続き受理しない。参照・捕捉対象の静的関係は保持するが、関数の生存期間・呼出環境の実現と Target での可否は Realization の責務とする。既存の `with` その他の意味契約は変更しない。

title: 関数値の受理境界と間接呼出の別契約

level: MUST

related: [CST_021](construct.md#cst_021)

## FRT_015

`Callable` の型が明示された変数・引数などの `f(args)`、および関数型を戻り値とする静的に解決できる式 `factory(args)(args)` は、`FunctionValueCall` として正規化する。callee を `Value` の子として保持し、その後に位置引数を順序付きで保持する。返り値が関数型なら再度の間接呼出にも利用できる。従来の宣言名による直接呼出は `FunctionCall` のままとし、その契約を変更しない。関数値を介して呼出を行う場合でも、Frontend はソースの関数本体を実行・関数値の行き先を推論しない。

title: 関数値を介する間接呼出の正規化

level: MUST

related: [CST_022](construct.md#cst_022), [CST_018](construct.md#cst_018)

## FRT_016

関数値を介する呼出では、callee の構造型に基づいて位置引数の個数と各 Value 型を厳密に検証する。キーワード引数、可変長引数、型が関数でない callee、未知の型形状は補完せず明示的に拒否する。関数値の参照・捕捉経路は静的な Model 情報として保持し、動的な関数オブジェクトの同一性や捕捉環境の寿命を Frontend は実行・予測しない。第11段階では新たな C/Python Target Realization を追加しないため、未対応 Realization を指定した生成は明示的に失敗する。既存 `with` 等の意味契約は変更しない。

title: 間接呼出の制限と Realization 境界

level: MUST

related: [CST_022](construct.md#cst_022), [CST_021](construct.md#cst_021)

## FRT_017

Frontend は既存の型付き `def`・`Callable`・`Reference`・`FunctionCall`・`FunctionValueCall` から逸出する関数値を正規化し、レキシカルな宣言所有経路と参照同一性を保つ。同一の関数宣言から複数回得られた関数値を一つの実行時環境に確定せず、呼出元と引数の式を個別の構造として残す。`nonlocal` / FRT_072 の範囲外の `global`、動的関数属性、宣言以前の外側ローカル参照、未対応の動的操作は引き続き拒否する。これらの静的な情報保持は実際の Target における捕捉環境の寿命・参照共有の検証を代替しない。既存 `with` 等の意味契約は変更しない。

title: クロージャー静的導線の保存と実行時環境の非推論

level: MUST

related: [CST_023](construct.md#cst_023), [CST_024](construct.md#cst_024)

## FRT_018

Python Frontend は組み込み `tuple[T1, T2, ...]` という固定長の明示アノテーションと `tuple[()]`（空）を `TupleType` に正規化する。式の `(a, b)`、`(a,)`、`()` は要素の順序・ネストを保つ `TupleValue` として解釈する。宣言・再代入、型付き関数の仮引数と戻り値、`typing.Callable` の型引数、関数値の受け渡しにタプル形状を伝播し、異なる位置の型・長さは拒否する。ソースの式や関数を実行せず、Target の格納方式を推測しない。

title: 固定長タプル式と明示型の正規化

level: MUST

related: [CST_025](construct.md#cst_025)

## FRT_019

タプル要素の参照は `t[0]` のようなリテラルの非負整数添字のみを受理し、型形状と範囲を検証して `TupleElement` とする。入れ子の参照や、関数値となるタプル要素の `t[0](args)` を受理するが、一般的な添字演算は推論しない。`tuple[T, ...]` のような可変長型、負数・動的添字、スライス、アンパック・要素への代入、Python の全コレクション意味論は未対応として明示的に拒否する。新しいタプル関連 Construct の Realization はこの段階では登録せず、対応しない Target Pack は実現時に拒否する。既存の `with` 等の意味論は変更しない。

title: タプルへの静的アクセスと受理範囲の制限

level: MUST

related: [CST_025](construct.md#cst_025), [CST_026](construct.md#cst_026)

## FRT_020

Frontend は Python AST の `try` / `except` / `else` / `finally` を `Try`、`ExceptHandler`、既存 `Block` の順序付き構造へ正規化する。各 `except` は `ValueError` / `TypeError` / `RuntimeError` の明示的な型名、またはその型名のみを含むタプルに限定する。`raise ValueError(...)` / `TypeError(...)` / `RuntimeError(...)` は、引数なしまたは静的に文字列型と判明する位置引数1個だけの `Raise` とする。これらの組込み名がソースの名前宣言・関数・import 等により隠されている場合は受理しない。例外オブジェクトの生成やメッセージ式の評価を Frontend は実行しない。

title: 限定された例外構文の静的正規化

level: MUST

related: [CST_027](construct.md#cst_027), [CST_028](construct.md#cst_028)

## FRT_021

`except ... as name` による例外値の束縛、裸の `except:`、再送出 `raise`、任意クラスの `raise`、`raise ... from ...` による原因連鎖、`except*` / 例外グループ、複数引数・キーワード引数・非文字列メッセージ、特殊な例外オブジェクトの操作は未対応として拒否する。`try` の各節で新しい型付き束縛やマップ済みオブジェクトの再束縛を行うことも既存の制御本体規則に合わせて拒否する。`return` / `break` / `continue` を含む制御移行は構造として保持し、Python の例外実行を推論せず Realization の責務に残す。新規例外 Construct の Target Realization は未登録とする。既存の `with`、関数、式、スコープの意味論を今回の原則に従って再解釈・変更しない。

title: 例外の受理境界と未対応 Realization

level: MUST

related: [CST_027](construct.md#cst_027), [CST_029](construct.md#cst_029)

## FRT_022

Python Frontend は組込み `list[T]` の明示型、同一要素型の `[value, ...]` を `ListType` / `ListValue` へ正規化する。型宣言・再代入、関数の引数・戻り値、`Callable` / `tuple` 内部の入れ子にも再帰的な要素型を伝播し、空の `[]` は期待されるリスト型が明確な宣言・代入・戻り値・関数の位置引数の場所でのみ受理する。`xs[index]` は整数式を保持する `ListElement`、`xs[index] = value` は既知のリスト名と整数添字・要素型が確認できる場合の `ListElementAssign` とする。入れ子関数から外側のリストへの要素更新は名前の再束縛とは異なるため、既存レキシカル参照を利用する。別名、負の添字、実行時の境界確認は Python ソースの意味契約として残し、Frontend で演算や境界検査を実行しない。

title: 型付き同種リストと要素変更の正規化

level: MUST

related: [CST_030](construct.md#cst_030), [CST_031](construct.md#cst_031)

## FRT_023

現段階では `list[T]` の単一の明示型引数、リストリテラル、整数添字での読み取り・変数上の要素更新だけを受理する。型推論のない空 `[]`、型不一致の要素、`append` / `extend` / `pop` 等の要素数変更、スライス、内包表記、アンパック、メソッド呼出、複合代入、型の無い一般的な Python コレクション操作は推論せず拒否する。`tuple` の静的添字・不変性は従来どおり維持する。新規リスト Construct の Target Realization は未登録であり、指定 Realization がリストの意味と参照共有を保証できなければ実現段階で拒否する。既存の `With`・例外処理・その他の構造について過去の設計判断を再解釈しない。

title: リストの受理境界と Realization の責務

level: MUST

related: [CST_030](construct.md#cst_030), [CST_031](construct.md#cst_031)

## FRT_024

Python Frontend は `dict[K, V]` の明示的な型アノテーション（K は `int` または `str`）と `{key: value, ...}` を `DictType` / `DictEntry` / `DictValue` へ正規化する。非空リテラルに期待型がなければ先頭要素のキー・値型から型形状を決め、すべてのエントリーをその形状で検証する。空リテラル `{}` は、宣言・代入・戻り値・位置引数など明示的な期待辞書型が得られる位置でのみ受理する。関数・Callable・リスト・タプル・辞書の内部へ再帰的に型形状を伝播させる。`d[key]` は `DictElement`、既知の辞書変数への `d[key] = value` は `DictElementAssign` として正規化する。既存のレキシカル束縛を利用し、外側の辞書の要素変更を再束縛と混同しない。Python の式は静的に実行しない。

title: 型付き辞書のリテラル・添字・更新の正規化

level: MUST

related: [CST_032](construct.md#cst_032), [CST_033](construct.md#cst_033)

## FRT_025

本段階で受理する辞書はキー型 `int` / `str`、単一の明示的値型、リテラル・型付き名前束縛・添字による読み取りと単純な辞書変数への要素追加/更新に限定する。複合・混合キー型、静的期待型のない空辞書、`{**mapping}`、dict 内包表記、`dict(...)` コンストラクタ、`get` / `update` / `pop` 等のメソッド、`del`、辞書反復、一般的なキー同一性推論や Python のリフレクションは受理しない。添字読み取りで存在しないキーの `KeyError` 契約は、現在の限定例外 Construct に新たな捕捉可能型を追加しない。辞書の Target Realization は未登録であり、順序・値更新・別名共有・検索失敗の意味を実現できない Target は明示的に拒否する。既存の `with`・タプル・リスト・例外の既定の意味契約は変更しない。

title: 辞書の限定された受理範囲と Realization 境界

level: MUST

related: [CST_032](construct.md#cst_032), [CST_033](construct.md#cst_033)

## FRT_026

Frontend はモジュール直下のクラスデコレータ・メタクラスを持たない `class`（静的単一継承は FRT_029〜031 に別途規定）を公称宣言として正規化し、各クラスに戻り値 `None` の明示的な `__init__` と通常の型付きインスタンスメソッドを要求する。メソッドの無注釈第一引数を所属クラス型の `ParameterRole.RECEIVER` に正規化し、名前が `self` 以外でも同じ役割を設定する。フィールドは `__init__` 冒頭（派生クラスでは必須の `super().__init__` 直後）の連続した `receiver.name: T = value` 宣言から静的に抽出し、初期化済みフィールドのみ参照させる。属性アクセス・代入、明示的な位置引数での生成とメソッド呼出を、型と宣言元に結び付けて Model 化する。対象のソースを実行せず、クラス構築・特殊メソッドを一般的に推論しない。

title: 静的クラス・型付きインスタンス・受取手の正規化

level: MUST

related: [CST_034](construct.md#cst_034), [CST_035](construct.md#cst_035), [CST_036](construct.md#cst_036)

## FRT_027

当面は公称インスタンス型、直接宣言されたフィールド・通常インスタンスメソッド、限定された生成/参照/更新だけを受理する。FRT_029〜031 で採用した静的単一継承と裸の `super()` 以外の継承機構、独自 `__new__`、`__init__` 以外の特殊メソッド、クラス属性、継承されたメソッド探索、`staticmethod` / `classmethod` / `property`、descriptor、`__getattribute__` / `__setattr__`、動的属性追加、デコレーター、クラスオブジェクトを値として操作する構文、受取手の再束縛、FRT_048 の範囲外のメソッド引数形式、条件的なフィールド宣言などを拒否する。クラス本体は直接宣言されたメソッドのみとし、メソッド名はクラスの専用名前空間に置く。メソッド本体で無修飾メソッド名を暗黙の関数参照として解決しない。一方、通常のモジュール関数への参照は既存レキシカル解決を維持する。

title: Python 動的クラス機構の限定的な採用境界

level: MUST

related: [CST_034](construct.md#cst_034), [CST_035](construct.md#cst_035)

## FRT_028

新しい `ClassDefinition` / `InstanceCreation` / `FieldRead` / `FieldWrite` / `FieldInitialize` / `MethodCall` に Target Realization は追加しない。対応しない Target Pack への変換は Realization 段階で明示的に失敗し、元の Model は変異しない。クラス名の公称型、受取手の役割、属性宣言元、値の参照共有などが保証されるべき契約である。新たなクラス採用判断は既存 `with`、関数、例外、タプル、リスト、辞書の意味契約を変更する理由にしない。

title: クラス関連 Realization の未対応境界と既存仕様の維持

level: MUST

related: [CST_034](construct.md#cst_034), [CST_036](construct.md#cst_036)

## FRT_029

`class Derived(Base)` は既に同一モジュールで定義された静的な単一基底クラス名だけを受理する。基底名はクラス式・動的演算ではなく AST の単純な Name であり、未定義・自己参照・多重継承・メタクラス・クラスデコレータは拒否する。Frontend は `InstanceType.base` と `ClassSignature.base` を一意に結び、継承フィールドやメソッドを再帰的な宣言参照で解決する。基底側が先に宣言されたことを要求するのはこの段階の Frontend の受理条件であり、Realization のメモリ配置を制限しない。

title: 静的単一継承の Frontend 受理境界

level: MUST

related: [CST_037](construct.md#cst_037)

## FRT_030

派生 `__init__` は先頭に引数なしの `super()` を介した `super().__init__(args)` を一度だけ要求する。`super()` の第2引数形式・動的な基底操作を受理せず、初期化呼出は同一 Receiver に対する静的な基底メソッド呼出であり新たな基底インスタンスを生成しない。新規の型付きフィールドはこの先頭呼出の直後に宣言し、継承されたフィールドの参照は親初期化後に許可する。通常の `super().method(args)` はクラス内の通常メソッドで受理し、当該メソッドのレキシカルな所属クラスから直上の基底を辿って静的に署名を解決する。`super().__init__` のメソッド外・コンストラクタ外利用は拒否する。

title: 親初期化と super の静的解決

level: MUST

related: [CST_038](construct.md#cst_038)

## FRT_031

インスタンスを型付きの基底型へ代入・引数渡し・返却することを許し、実クラスを AST から推測して固定しない。通常の `obj.method(args)` は、静的な受取手型でアクセス可能なメソッド署名を検証する `MethodDispatch.VIRTUAL` 呼出へ正規化する。Realization は実行時の実クラスと静的な継承階層から適切な実装を選択する責務を持つ。派生クラスによる `__init__` 以外のオーバーライドは型形状を一致させる。無関係の公称型・逆方向の暗黙変換・不一致のオーバーライド・静的クラス外の super・対応しない Target 実現を明示的に拒否する。既存の with 等の意味論は変更しない。

title: 静的クラス階層での仮想呼出と未対応境界

level: MUST

related: [CST_037](construct.md#cst_037), [CST_038](construct.md#cst_038), [CST_039](construct.md#cst_039)

## FRT_032

型が静的に分かるインスタンス値を、単純名とコンストラクタに加えて、型付きリスト・辞書・固定長タプルの要素参照、関数やメソッドが返す値、インスタンスフィールドの連鎖からメソッド受取手として受理する。Frontend はこれらの式を Python として実行せず、値式を `MethodCall.receiver` の子構造へ保持する。静的受取手型から宣言済みメソッドを検証し、通常呼出は常に `MethodDispatch.VIRTUAL` とする。実際のインスタンス型と実装選択は Realization の責務であり、静的な推測で決め打ちしない。

title: 複合式から得た型付きインスタンスの仮想メソッド呼出

level: MUST

related: [CST_040](construct.md#cst_040), [CST_038](construct.md#cst_038)

## FRT_033

インスタンスの `obj.member(args)` について、静的に確定した `member` が通常のメソッドであれば従来の仮想 `MethodCall`、明示的な `Callable` 型のフィールドであれば `FieldRead` を callee とする `FunctionValueCall` に正規化する。継承された関数型フィールドの宣言元情報を保持し、後者に Receiver を暗黙追加しない。インスタンスフィールドの連鎖も既存の `FieldRead` により表現する。関数値呼出の引数個数・型・位置引数のみの制約は変更しない。`super()` 呼出は従来の `MethodDispatch.SUPER` を維持する。

title: メソッド呼出と関数値フィールド呼出の区別

level: MUST

related: [CST_041](construct.md#cst_041), [CST_022](construct.md#cst_022), [CST_038](construct.md#cst_038)

## FRT_034

型を確定できない受取手、未定義メンバー、非 Callable フィールドへの呼出、引数個数・型不一致、未対応のキーワード・展開引数、逆方向の公称型変換は引き続き拒否する。タプル・リスト・辞書の既存の形状規則と、要素代入先を単純な宣言済みリスト/辞書変数に限定する規則は変更しない。複合参照を受理しても Target Realization は新設せず、クラス・継承・関数値・コレクションの実現が不足する場合は明示的に失敗する。既存 `with` 等の意味論も変更しない。

title: クラスと複合値の境界検証および未対応 Realization

level: MUST

related: [CST_040](construct.md#cst_040), [CST_041](construct.md#cst_041)

## FRT_035

Python AST の厳密な bool 定数 `True` / `False` は整数 `Literal` でなく `BooleanLiteral` へ正規化する。Boolean 型宣言・再代入、`if` / `while`、既存 `BooleanOperation` / `BooleanNot` の Boolean オペランドとして受理する。Python の一般的な truthiness や bool/int 間の暗黙の型互換は採用せず、整数が必要な位置に bool 定数が現れた場合は型不一致で拒否する。

title: Boolean 定数の型付き正規化

level: MUST

related: [CST_042](construct.md#cst_042)

## FRT_036

Python AST の `None` 式は原則として `NoneLiteral` Value へ正規化する。明示 `object` / `typing.Any` の変数と関数の引数・戻り値に許す一方、宣言型 `None`、暗黙の `Optional` / `Union`、既存 `list[T]` / `dict[K,V]` / 固定タプルの要素型規則の一般化は行わない。既存の `-> None` 関数の `return` および `return None` は、以前と同じ `Return()` のままとする。`None` を他の型へ黙って変換せず、不整合は明示的に拒否する。

title: None を一般式 Value として扱う限定範囲

level: MUST

related: [CST_043](construct.md#cst_043)

## FRT_037

`a if condition else b` (`ast.IfExp`) は `ConditionalExpression` に正規化し、`condition` は厳密に `ValueKind.BOOLEAN` とする。宣言・代入・関数引数/戻り値などに明示の期待 `ValueType` がある場合は、その型に双方の枝が適合することを検証する。期待型がない場合は両枝の `value_type` の厳密な一致を要求する。型推論による暗黙の合流型・Union は構築しない。条件と枝の AST は実行せず、実行順と非選択枝の非評価を Model に保持する。

title: 条件式の静的な型検証と AST 正規化

level: MUST

related: [CST_044](construct.md#cst_044)

## FRT_038

Boolean 定数・None 値・条件式の導入を理由に、既存 `Literal`、`Return`、`With`、例外、型付きコレクションやクラスの過去の意味契約を再解釈しない。Python の任意の truthiness、動的な Union/Optional や型推論、Boolean の整数扱い、今回追加した3構造への Target Realization は未対応であり、明示的な型不整合は Frontend が、欠落する Target 実現は Realization が拒否する。

title: 3機能の受理境界と Realization 未対応

level: MUST

related: [CST_042](construct.md#cst_042), [CST_043](construct.md#cst_043), [CST_044](construct.md#cst_044)

## FRT_039

既存の宣言や import により上書きされていない `len(expression)` を `Length` に正規化し、位置引数ちょうど1個と `str` / `tuple` / `list` / `dict` の静的な型だけを受理する。Python AST から対象式の構造を保持し、文字列やタプルの長さを事前評価しない。明示型を持たない `object` / `Any`、ユーザー定義クラス、キーワードや `*args`、引数個数の不一致は明示的に拒否する。Python の任意の `__len__` の解決機構は導入しない。

title: len 組み込み構文の限定的な正規化

level: MUST

related: [CST_045](construct.md#cst_045)

## FRT_040

名前が未束縛の直接呼出 `abs(x)` を整数 `Absolute`、`min(a, b, ...)` / `max(a, b, ...)` を整数 `Extremum` に正規化する。`abs` は位置引数1個、`min` / `max` は2個以上の位置引数を要求し、すべてのオペランドは厳密に `ValueKind.INTEGER` とする。演算対象の式と引数の順序は保持し、Frontend は値を計算しない。呼出先のユーザー定義関数、関数型変数、登録済みのマッピング の同名参照が存在する場合は、それらの従来の解決を優先する。

title: 整数 abs・min・max の型付き正規化

level: MUST

related: [CST_046](construct.md#cst_046), [CST_047](construct.md#cst_047)

## FRT_041

新しい基本操作は Python 組み込み関数全体の導入ではない。未採用の `zip` / `enumerate` など、浮動小数点・一般オブジェクトへの abs、Iterable 1引数 min/max、`key=` / `default=`、動的属性参照や特殊メソッドによる拡張は扱わない。`Length` / `Absolute` / `Extremum` の Realization は提供せず、Model を生成できても対応する Target Realization がなければ明示的に失敗する。既存の `Range` / `Call` / `With` および既存演算・コレクションの意味論をこの実装を理由に変更しない。

title: 基本組み込み操作の採用境界と Realization の拒否

level: MUST

related: [CST_045](construct.md#cst_045), [CST_046](construct.md#cst_046), [CST_047](construct.md#cst_047)

## FRT_042

未束縛の直接呼出 `sum(iterable)` および `sum(iterable, start)` を `IntegerSum` へ正規化する。`iterable` は `list[int]`、全要素が `int` の固定長タプル、既存の整数 `range(...)` に限定し、`start` は整数 Value とする。省略開始値を明示的な呼出副作用として合成しない。引数は位置指定1個または2個のみ。反復元と開始値の式・評価順は保持し、Frontend は集約を実行しない。型無し空リスト、文字列、dict、Boolean 等の `sum` は明示的に拒否する。

title: 整数 sum の限定的な AST 正規化

level: MUST

related: [CST_048](construct.md#cst_048)

## FRT_043

未束縛の直接呼出 `any(iterable)` / `all(iterable)` を `BooleanAggregate` へ正規化する。位置引数1個のみとし、要素が厳密な Boolean 型の `list[bool]` または固定長タプル（空タプルを含む）だけを受け入れる。Boolean の一般的な truthiness へ拡張せず、短絡評価は Model の契約として保持する。引数式は実行・定数畳み込みしない。

title: any/all の Boolean 限定正規化

level: MUST

related: [CST_049](construct.md#cst_049)

## FRT_044

`sum` / `any` / `all` の名前が既存の関数宣言、型付き関数変数または登録済みのマッピング として解決できる場合は、その既存経路を優先し組み込み操作として横取りしない。キーワード引数、展開引数、未宣言の汎用 Iterable、非対応の要素型や引数個数は明示的に拒否する。`IntegerSum` / `BooleanAggregate` の Target Realization はまだ提供せず、Model 正規化可能であっても生成先での実行は保証しない。既存の `Range` / `Call` / `With` / `Length` / `Absolute` / `Extremum` の意味論には変更を加えない。

title: 集約組み込み操作の名前解決と Target 境界

level: MUST

related: [CST_048](construct.md#cst_048), [CST_049](construct.md#cst_049)

## FRT_045

Python AST の `float` 型注釈と有限な float リテラルを `ValueKind.FLOAT` / `FloatingLiteral` に正規化する。`+` / `-` / `*` / `/`、単項符号、同種 float 比較を専用 Construct へ変換し、関数・Callable・コレクションで既存の静的型検証を適用する。整数と float の暗黙変換、float `//` / `%`、複素数、`float()` コンストラクタ呼出は採用しない。

title: 浮動小数点の型・式の正規化

level: MUST

related: [CST_050](construct.md#cst_050), [CST_051](construct.md#cst_051), [CST_052](construct.md#cst_052)

## FRT_046

`str + str` を `StringConcat`、`str * int` / `int * str` を `StringRepeat`、str 同士の6種比較を `StringComparison`、`str in str` / `str not in str` を `StringContains`、`str[int_expr]` を `StringElement` に正規化する。String 値・添字式・比較式を AST から保持し、Python の文字列を Frontend で計算しない。連鎖比較・スライス・任意の動的オブジェクトの属性処理は対象外とする。

title: 文字列基本演算と静的な型検証

level: MUST

related: [CST_053](construct.md#cst_053), [CST_054](construct.md#cst_054), [CST_055](construct.md#cst_055)

## FRT_047

新しい浮動小数点・文字列 Construct は既存の `Literal`、整数 `Arithmetic`、整数限定の `Absolute` / `Extremum` / `IntegerSum`、`Length`、`With` 等の意味契約を変更しない。新規構造の Realization はまだ提供せず、Target が Python float の演算・文字列 Unicode/IndexError の契約を満たせなければ明示的に失敗する。Python の一般オブジェクトプロトコルや精度指定用 Interface を推測して追加しない。

title: 文字列・浮動小数点の受理制限と Target 境界

level: MUST

related: [CST_050](construct.md#cst_050), [CST_053](construct.md#cst_053), [CST_055](construct.md#cst_055)

## FRT_048

静的に宣言が解決できる `FunctionCall`、クラス生成 `InstanceCreation`、受取手を持つ `MethodCall`（通常/`super()`）に限り、通常の位置引数と名前指定のキーワード引数を混在して受理する。仮引数名へ静的に対応付けて `arguments` を宣言順に並べ、Python AST での位置引数、続くキーワード引数の式評価順を `evaluation_order` に別途保持する。受取手式は呼出の引数式に先行して一度評価される。型付けと宣言スコープ、仮想/`super()` ディスパッチの既存契約は変えない。

title: 静的なキーワード引数と記述順の分離正規化

level: MUST

related: [CST_056](construct.md#cst_056)

## FRT_049

不明なキーワード名、重複束縛、必須引数の不足、型不一致、過剰な位置引数、`*args` / `**kwargs` 展開は、推論せず明示的に拒否する。`CallableType` は仮引数名を持たないため、`FunctionValueCall` に対するキーワード引数は引き続き対象外である。組込み操作、マップ済み関数の特殊な呼出、FRT_050〜051 で認めない一般的なデフォルト式、位置専用・キーワード専用引数、動的な関数変換も今回の対象外とする。対応する Target Realization がない場合は拒否する。新しい契約の追加を理由に、既存の `With`、数値・クラス・クロージャーの意味論を再解釈しない。

title: キーワード引数の制限・静的型検証と実現責務

level: MUST

related: [CST_056](construct.md#cst_056)

## FRT_050

Frontend は位置引数を受ける型付き `def` とインスタンスメソッド（`__init__` および `super()` 経由の呼出を含む）について、末尾の引数に対する整数・有限 float・文字列・Boolean・None のリテラルデフォルトを受理する。単項 `+/-` を伴う整数/float リテラルも受理するが、算術式、名前参照、関数呼出、リスト・辞書・タプル等の複合デフォルト、`*args` / `**kwargs`、位置専用・キーワード専用引数は拒否する。型に合わないデフォルトは拒否し、`None` デフォルトは `object` または明示 `Any` 型でのみ受理する。関数宣言の収集段階で値を静的に正規化し、入力コードを実行しない。

title: 限定された静的デフォルト引数の受理と拒否

level: MUST

related: [CST_057](construct.md#cst_057)

## FRT_051

Frontend は宣言が静的に確定する直接関数呼出、インスタンス生成、通常/`super()` のメソッド呼出で、省略された仮引数を宣言済みの不変リテラルで補う。`arguments` の全 Slot は従来どおり仮引数順で値を持ち、`omitted_arguments` は省略箇所、`evaluation_order` は明示実引数の評価順に続く省略リテラルの位置を保持する。Realization は呼出対象/Receiverを一度評価し、ソースに書かれた引数式だけをその記述順に一度ずつ評価し、静的なデフォルト値で不足引数を補う。一般的な Python 定義時の式評価、可変デフォルトの共有、`CallableType` の引数数推論による間接呼出の省略、デコレーターによる暗黙の書換は含めない。オーバーライドによるデフォルト値の変更は、基底型の参照から呼び出した場合の不一致を避けるため拒否する。既存の `With` や他の Construct の意味は変更しない。

title: 呼出ごとの省略補完と明示実引数の評価順

level: MUST

related: [CST_056](construct.md#cst_056), [CST_057](construct.md#cst_057)

## FRT_052

Frontend はクラス本体の通常の型付き `def` に付く、隠されていない組込み `@staticmethod` だけを `MethodKind.STATIC` として受理する。Receiver のない引数はすべて明示型を要求し、呼出は `ClassName.method(...)` 形式で静的にクラス名・メソッド宣言を解決する。仮引数の型・名前付き引数・限定されたデフォルト値と評価順序を保持する。インスタンス経由の staticmethod アクセス、staticmethod を値として取り出す操作は初期契約に含めない。

title: 選択的 staticmethod の静的正規化

level: MUST

related: [CST_058](construct.md#cst_058)

## FRT_053

Frontend は `@classmethod` で修飾された型付きメソッドに、第一仮引数の綴りに依存しない `CLASS_RECEIVER` 役割を付与する。`ClassName.method(...)` とメソッド内部の `receiver.method(...)` をクラスメソッド呼出として正規化し、`receiver(args...)` を `ClassReceiverCreation` に正規化する。静的な単一継承で基底に宣言された classmethod が派生クラスから呼ばれる場合、実行時のクラスを派生先として維持し、関数本体へ基底のインスタンスを固定的に生成する意味は採用しない。任意のクラスオブジェクト参照・リフレクション・メタクラス・インスタンス経由の classmethod 呼出は受理しない。

title: クラス受取手の動的な同一性と限定操作

level: MUST

related: [CST_059](construct.md#cst_059)

## FRT_054

Frontend は先頭で明示的に `from dataclasses import dataclass`（別名可）を import し、装飾対象が未継承のクラスで、そのデコレータ名が隠されていない場合だけ `@dataclass` を受理する。クラス本体の型付き `name: T` または `name: T = scalar_default` を宣言順に収集し、静的な初期化メソッドと既存 FieldInitialize を構築する。デフォルトなしのフィールドをデフォルト付きフィールドの後に置くこと、`__init__` の独自定義、任意のデフォルト式、`field()`、dataclass オプションは拒否する。合成された初期化には既存のインスタンス生成・デフォルト値・キーワード引数の意味契約を適用する。

title: 限定 dataclass フィールドと生成初期化

level: MUST

related: [CST_060](construct.md#cst_060), [CST_057](construct.md#cst_057)

## FRT_055

一般の Decorator AST、デコレーター関数の評価・適用・戻り値による置換、Python の descriptor / metaclass / dataclass の完全意味論を推論しない。既存の通常インスタンスメソッド・継承・`with` 等の契約は維持する。静的メソッド・クラスメソッド・限定 dataclass は別の Model 契約とし、対応する Target Realization がない場合は明示的に失敗する。

title: 選択的デコレーターの採用境界と実現責務

level: MUST

related: [CST_058](construct.md#cst_058), [CST_059](construct.md#cst_059), [CST_060](construct.md#cst_060)

## FRT_056

Python Frontend は `ast.Lambda` を、宣言・戻り値・引数・型付きコレクション要素・型付き条件式などの文脈から明示的な `Callable[[...], R]` 期待型が確定する場合に限り `LambdaValue` へ正規化する。ラムダの無注釈の仮引数は `CallableType.parameter_types` に一対一で型付けし、単一式の結果は `CallableType.return_type` へ照合する。ラムダの各式には衝突のない生成名と独立したレキシカルスコープを与え、外側の `Symbol` / 関数宣言への参照を保持する。ラムダ内のラムダ、戻り値としての関数値、型付きの関数引数やリスト/タプル要素も既存構造を利用する。ソースを実行したり戻り値型を任意に推論したりしない。

title: 明示 Callable 文脈での lambda の型付き正規化

level: MUST

related: [CST_061](construct.md#cst_061), [CST_020](construct.md#cst_020), [CST_023](construct.md#cst_023)

## FRT_057

ラムダの型を確定できない式位置、引数個数の不一致、デフォルト引数、位置専用/キーワード専用引数、可変長引数、実引数展開、式本体の型不一致や未解決名前は明示的に拒否する。`None` を返すラムダは本体の `None` 式だけを採用する。一般的な Python の関数オブジェクト属性・動的なデコレーター機構は受け入れない。ラムダの定義/捕捉/関数値の Target Realization は本段階で提供せず、未登録の場合は変換時に明示的に拒否する。既存の `with`、クラス、デフォルト引数等の意味契約を変更しない。

title: ラムダの受理範囲と Realization との境界

level: MUST

related: [CST_061](construct.md#cst_061)

## FRT_058

デコレーターの識別は `DecoratorRegistry` に登録された完全修飾名・適用対象（class / method / function）・明示的な効果名で行う。明示 import の別名は解析単位で独立して束縛し、組込み staticmethod / classmethod と import 済み dataclass は登録済み規則として解決する。識別ルールの登録と、対象・効果に対応する正規化ハンドラーの登録を別々に行い、後者がない場合は必ず拒否する。method のハンドラーは `MethodKind` を確定し、class のハンドラーは既存 Construct に正規化される追加メソッド等を `ClassDecorationPlan` で宣言し、function のハンドラーは構築済み `FunctionDefinition` を同じ署名の `FunctionDefinition` へ変換できる。class の正規化計画は解析単位の同じ宣言に対して一度だけ導出する。組込み3種も同じハンドラー機構で扱い、既存の意味契約と拒否条件は FRT_052〜055 に従う。動的なデコレーター呼出・評価、複数デコレーター適用順序の一般化、ハンドラーを登録せずに Python の意味を推測することはしない。構築する Model の意味を定めるのは明示登録されたハンドラーであり、Target での実現可否は Realization に委ねる。ハンドラーの現行返値型の範囲を超える Construct / Interface への一般的な置換は未実装である。

title: 登録型デコレーター識別と効果正規化の境界

level: MUST

related: [CST_058](construct.md#cst_058), [CST_059](construct.md#cst_059), [CST_060](construct.md#cst_060)

## FRT_059

Python Frontend は `ast.Pass` を出現位置に対応する `Pass` へ正規化する。モジュール、型付き関数・メソッド、静的クラス宣言の各本体について、最初の文が文字列定数式である場合だけ docstring として認識し、値の文字列を対応する Model 宣言の `docstring` に保持して実行文から除く。クラス宣言および限定 `@dataclass` の先頭 docstring は型付きフィールド定義やメソッド数として数えず、`__init__` の先頭 docstring は既存の初期化順序検証を変えない。先頭以外の独立した文字列式、f-string、一般の文字列式評価は新たに受理しない。文書の有無から Target での `__doc__` 属性の生成や Python の内省機構を推論せず、未登録の `Pass` Realization が必要な変換は従来の未登録拒否に従う。

title: pass と宣言docstringの限定的正規化

level: MUST

related: [CST_062](construct.md#cst_062)

## FRT_060

Python Frontendは `ast.AugAssign` の対象が既宣言の通常名、または静的に型解決できるインスタンスフィールドであり、かつ `int` または `float` の同一型スカラー演算が成立する場合だけ `AugAssign` として正規化する。フィールドReceiver式は一度だけ正規化し、元の代入先を右辺の式へ複製しない。整数は `+=` / `-=` / `*=` / `//=` / `%=` と FRT_062 のビット演算型複合代入、floatは `+=` / `-=` / `*=` / `/=` を受理する。`ast.AugAssign` の名前ターゲットもPythonの関数ローカル名の事前予約に含め、明示 `global` がない関数内複合代入を同名のモジュール変数または外側関数の値に誤解決しない。FRT_072で許可された明示的global名については、元のモジュールSymbolを保持した既存AugAssignを受理する。未宣言名、インスタンスReceiverの再束縛、初期化前のフィールド使用、リスト・辞書の `+=`、要素添字への複合代入、累乗などは明示的に拒否する。通常の代入・フィールド更新、例外経路、既存型契約は変更しない。

title: 限定スカラーAugAssignの静的正規化

level: MUST

related: [CST_063](construct.md#cst_063)

## FRT_061

Python Frontendは比較演算子が2個以上連続する `ast.Compare` を、全オペランドの型が厳密に一致する `int` / `float` / `str` かつ演算子が順序・等値比較の6種類に限定される場合だけ `ComparisonChain` へ正規化する。各オペランドの構築済みValueを原順序のまま一度ずつ保持し、二項比較やBoolean式を複製して作成しない。単一の既存Comparison / FloatingComparison / StringComparisonの正規化は維持する。混在型、`in` / `not in` / `is` / `is not` が混在するチェーンや任意の比較プロトコルは推論せず拒否する。

title: 静的スカラー比較チェーンと既存二項比較の区別

level: MUST

related: [CST_064](construct.md#cst_064)

## FRT_062

Python Frontend は、明示的に整数型と判明した2つの Value の `/` を `IntegerTrueDivision` に正規化し、結果型を `float` とする。`int` 型変数への暗黙の狭義化、混在型の `/`、式値の事前計算を認めない。整数同士の `&` / `|` / `^` / `<<` / `>>` と、整数の `~` を型付きの既存 `Arithmetic` / `IntegerUnary` に正規化する。負のシフト回数や巨大な整数についてソース式を実行・推論せず、実行上の意味契約を維持する。既宣言整数名・型付きフィールドの `&=` / `|=` / `^=` / `<<=` / `>>=` は `AugAssign` とし、既存のスカラー再束縛の意味契約に従う。浮動小数点のビット演算、暗黙の bool→int、整数とfloatの混在、累乗 `**` と `**=`、整数の `/=` は引き続き拒否する。標準Python/C Target Packへ新規Realizationを要求しない。

title: 整数同士の真の除算と型付きビット演算の正規化

level: MUST

related: [CST_065](construct.md#cst_065)

## FRT_063

`PythonFrontend(intrinsics=IntrinsicRegistry(...))` は指定表に明示登録された基本操作だけを、解決済みの静的な型署名に基づき `IntrinsicCall` へ正規化する。intrinsics引数省略時はFRT_065の既定提供者表を用いる。従来の `len` / `abs` / `min` 等の専用Constructによる処理は維持し、Pythonの一般的な組込み関数・属性を無条件には自動採用しない。直接名の呼出は同名の宣言済み関数・型付きシンボル・マップ済みの名前・クラス等を優先し、明示登録された非衝突の名前だけを基本操作とする。属性呼出は、先に既存の静的インスタンスメソッド・super・クラスメソッドを解決し、残る静的な型付きReceiverだけを登録表の `(Receiver型, 名前)` で厳密に照合する。Receiverを二度正規化せず、位置引数の個数と型を確認する。未登録名、キーワード引数、引数展開、一般的なオーバーロード推論、暗黙の型変換、Python実装の任意メソッドの実行は拒否する。`convert(intrinsics=...)` は明示的な提供者表をFrontendへ渡せるが、Realizationは独立しており、標準C/Python Packには新しい実現規則を追加しない。

title: 型付き基本操作の登録照合とFrontendの限定正規化

level: MUST

related: [CST_066](construct.md#cst_066)

## FRT_064

提供者が `IntrinsicRegistry` に同一キーの複数シグネチャを明示登録した場合、Python Frontend は構築済みの既知Receiver型と位置引数型から候補を厳密に絞り、ただ一つに適合する署名だけを `IntrinsicCall` とする。Receiver・引数を候補数に応じて再度正規化しない。候補が一つなら既知のReceiverから具体化できる型を期待型として式の構築に使えるが、候補が複数のときは期待型を推測せず、文脈型がないと正規化できない式は拒否する。型変数の束縛は署名内の明示型の照合のみで、型の昇格・候補順位付けや一般的なPython型推論は行わない。戻り値は選択済み署名から静的に決まり、提供者登録の有無と既存宣言の優先関係を維持する。戻り値がNoneの型付き基本メソッドの式文も構築できるが、Python/C標準Target Packに新しいRealizationは追加しない。

title: 複数署名の一意な静的照合と署名内型変数の具体化

level: MUST

related: [CST_067](construct.md#cst_067)

## FRT_065

`PythonFrontend()` は既定で `standard_intrinsics()` を用い、`str()` / `int()` / `float()` の引数なしと、明示型 `int` / `float` / `str` / `bool` の1引数呼出、および静的な `str` Receiverの `upper()` / `lower()` を、選択済み `IntrinsicDefinition` を持つ `IntrinsicCall` に正規化する。型変換前後の型と個別obligationsはCST_068の提供者宣言によって決まり、入力値を実行せず、変換例外や大小文字のUnicode展開を推測しない。明示的に `intrinsics=IntrinsicRegistry(...)` を指定した場合は既定表を置き換え、`standard_intrinsics().extend(...)` で明示的に拡張できる。同名のユーザー宣言と既存のマップ済みの名前/クラス優先、曖昧候補の拒否、キーワード・展開引数の拒否を維持する。複数引数の `int(str, base)`、登録していない型・メソッド、動的な型変換と書式指定は受理しない。Python/C標準Target Packには今回のIntrinsic実現レシピを登録せず、構築可能であることと出力可能であることを区別する。

title: 標準変換・Unicode文字列操作の静的正規化

level: MUST

related: [CST_068](construct.md#cst_068)

## FRT_066

Python Frontendは `ast.JoinedStr` から、リテラル断片と型付き `str(x)` IntrinsicCall断片からなる `FormattedString` を作る。各埋め込み式は一度だけ正規化し、標準または明示指定したIntrinsicRegistryの`str`署名を静的に解決する。`!s`と既定の変換のみを受理し、`!r`、`!a`、format spec、未登録型・曖昧な文字列化を拒否する。`print()`、複数位置引数、int/float/bool/strの単独引数は `PrintValues` とし、各値を同じ型付き文字列化署名へ正規化する。既存の単一文字列 `print(str_value)` は従来の `Call` へ正規化し、旧Packとの互換性を維持する。動的な `sep` / `end` / `file` / `flush`、引数展開、キーワード指定、任意のオブジェクト出力は拒否する。値の評価・書式化は実行せず、新規ModelにPython/C PackのRealizationを必須としない。

title: 限定f-stringと型付きprintの静的正規化

level: MUST

related: [CST_069](construct.md#cst_069)

## FRT_068

Python Frontendは二項比較の `in` / `not in` について、左式を
先に、右式を後にそれぞれ一度だけ正規化する。右式が型付きListまたは
DictならCST_071の `Membership` を構築し、型とキー型の不一致は拒否
する。右式がStringの場合、従来の `StringContains` を保持する。
未対応の右式、入れ子の動的containsプロトコル、所属を含む比較チェーンは
拒否する。新しいPython/C Packレシピはこの工程で登録しない。

title: 型付きList・Dict所属判定の静的正規化

level: MUST

related: [CST_071](construct.md#cst_071)

## FRT_067

Python Frontendは単一の代入対象が括弧付きまたは括弧なしの固定長Tupleであり、各要素が既宣言の通常型付き名前である場合に限り、`ast.Assign` を一つの `UnpackAssign` に正規化する。右辺は一度だけ正規化し、静的な `tuple[T1, ...]` の形状から要素数と代入型を検証する。`a, b = b, a`、型が異なるTuple変数からの代入、重複対象を受理する。新規名の暗黙宣言、入れ子・スター付き・List対象・属性・添字へのアンパック、複数対象への連鎖代入、マップ済みオブジェクトの再束縛、未知のTuple形状は拒否する。代入後のSymbolを再作成せず、Targetの一時領域を生成しない。Python/C Packに対応レシピを必須とはしない。

title: 既宣言名への固定長Tupleアンパックの正規化

level: MUST

## FRT_069

Python Frontendは `ast.Subscript` の `ast.Slice` を、対象が型付き `list[T]` または `str` である場合だけ `SliceValue` に正規化する。対象を一度だけ正規化し、開始・終了・ステップの存在する式をソース順で一度ずつ正規化する。各境界は既知の整数Valueに限定し、`bool`、`float`、未解決名は拒否する。省略された境界を整数0や長さへ補完しない。特に `s[::-1]` と `s[0::-1]` は異なるModelを生成する。定数0のステップも実行時の `ValueError` 契約として保持する。既存の単一添字参照、List/Dict更新やTupleの静的添字アクセスは変更しない。辞書・Tuple・非シーケンスのスライス、スライス代入は未対応。Target Packのレシピ追加を必須としない。

title: List・Stringの省略保持スライス正規化

level: MUST

related: [CST_072](construct.md#cst_072)

## FRT_070

単一名の `for name in source` で `name` が現在の宣言表に存在しないとき、反復元の静的に既知の要素型を厳密に一意に確定できる場合だけ、新しい型付き Symbol を反復入口で導入する。対象は整数 `range`、文字列、要素型既知の `list[T]`、すべての要素型が同一の非空固定長 `tuple` に限る。型が混合した tuple、空 tuple、形状不明のIterable、辞書、予約名、非反復可能値は暗黙導入しない。ソース式は導入前の名前環境で一度だけ正規化する。導入したSymbolはループ本体中の参照と再代入にだけ利用でき、`else` 内やループ終了後からの参照は今回の受理範囲として拒否する。これはPythonのif/forに新しいレキシカルスコープがあるという主張ではなく、未束縛の可能性を解析せずに済ませるFrontendの受理制限である。先に宣言された反復変数は従来どおり同じSymbolを更新し、ループ後にも参照できる。空反復時の偽の初期化、反復ごとに別Symbolを導入する処理、一般的なdefinite-assignment解析、動的な型推論を行わない。ModelにはCST_073の導入区別を保持し、新規束縛へのTarget Packの対応は必須としない。

title: 既知要素型からのfor変数の限定的な暗黙導入

level: MUST

related: [CST_073](construct.md#cst_073), [CST_004](construct.md#cst_004)

## FRT_071

`if` / `else`、`while` / `else`、`for` / `else` および `with` の制御本体において、型注釈と初期値が明示された通常の新規値名の `AnnAssign` を `Initialize` として受理する。各宣言は元の `Block` 内の実行位置に留め、宣言より後の同じ本体、またはその中の入れ子制御本体にある参照・再代入だけを許す。異なる分岐・ループの `else`・本体終了後からの新規名の参照は、Pythonでは束縛され得ても、一般的な経路別初期化解析を行わないため受理しない。これは新しいPythonのレキシカルスコープではなく、受理する参照位置の制限であり、Symbolの所有経路は既存の関数/モジュールのままとする。既宣言名の参照・再代入は従来どおり許す。新規制御ローカル名やFRT_070の新規反復変数をlambdaで捕捉する形式は、束縛寿命が本体を越える可能性があるため拒否する。関数定義の制御本体への配置、マップ済みオブジェクトの宣言・再束縛、try/except/finally直下の新規名、スコープを跨ぐ別名の一般的な初期化解析、未注釈の暗黙宣言は今回拡張しない。新しいConstruct/Targetレシピを導入せず、既存のBlock・Initialize・Symbolを再利用し、標準Packの新規意味対応の宣言は追加しない。

title: 制御本体内で使用が完結する型付き値宣言

level: MUST

related: [CST_002](construct.md#cst_002), [CST_003](construct.md#cst_003), [CST_073](construct.md#cst_073)

## FRT_073

Python Frontendはトップレベルの明示的な型付き関数の `def f(a: T, *rest: U) -> R:` および固定引数のない `def f(*rest: U) -> R:` を受理する。`U` は静的な通常値型であり、関数内の `rest` は `tuple[U, ...]` の一つの不変Tuple Symbolに束縛する。固定引数・末尾の不変リテラル既定値・0個以上の明示位置引数・固定引数へのキーワード束縛を型・重複・不足とともに検証する。引数式はソース順に一度だけ正規化し、固定引数の束縛順への並べ替えは既存の `evaluation_order` に記録する。`len(rest)`、`sum(rest)` の既存型適合、`for item in rest` の同種要素型による反復を受理する。可変長タプル注釈 `tuple[T, ...]` は固定長Tupleとは区別し、要素型が適合する固定長Tuple値からの代入を受理する。今回の範囲では可変長Tupleの添字アクセス、静的アンパック、`def` 以外の動的引数展開 `f(*rest)`、`**kwargs`、キーワード専用引数、メソッドや入れ子関数の可変長仮引数、可変長関数の第一級関数値化を拒否する。C Targetへの関数・可変長Tupleの実現規則は追加せず、対応するTargetの明示的なAdmission支持が必要である。

title: 自作関数の静的な型付き可変長位置引数

level: MUST

related: [CST_074](construct.md#cst_074), [CST_017](construct.md#cst_017)

## FRT_072

トップレベルの型付き `def` の先頭（任意のdocstringの直後）に並んだ `global name[, ...]` 宣言だけを受理する。各名前は関数定義より前に入力モジュールのトップレベルで型付き初期化済みの通常 `ValueType` 変数でなければならず、未知名、後方宣言、マップ済み型、引数との衝突、重複宣言、同じ関数内での型付き再宣言・関数名との衝突を拒否する。宣言は関数スコープ全体の名前束縛にのみ作用し、実行Constructを追加しない。宣言された名前の読み取りと単純な `name = value` は、モジュールの元の `Symbol` を参照する `Reference` / `Assign` へ正規化し、従来の型一致と初期化規則を維持する。さらに既存FRT_060に従うint/floatのスカラー複合代入 `name += value` 等も、同じ元のSymbolを指す `AugAssign` として受理し、target_once・read_before_rhs・rebindの既存意味契約を維持する。通常の関数内からモジュール変数へ再代入するには明示 `global` が必要であり、`global` のない複合代入は関数全体でローカル束縛名とみなし、未宣言・初期化前なら外側にフォールバックせず拒否する。条件分岐内での既宣言名への代入は可能だが、`global` 自体を制御本体の内側や関数の途中に配置する構文は受理しない。ネストした関数とメソッド内の `global`、`nonlocal`、`global` 名を `for` 対象・型付き再宣言する操作、新規モジュール名の暗黙作成、非対象のPython束縛構文は拒否する。文字列・リスト等の非スカラー複合代入もFRT_060に従い拒否する。`Symbol.scope == ()` と宣言オブジェクト同一性は維持され、ModelにPython固有のGlobal Constructを追加しない。共有状態の格納場所、関数呼出での副作用・順序をTargetが正しく実現できるかは別の契約であり、未実装のC Target等では失敗を維持する。

title: 明示的globalによる既宣言モジュール変数への限定的再代入

level: MUST

related: [CST_002](construct.md#cst_002), [CST_003](construct.md#cst_003), [CST_017](construct.md#cst_017)

## FRT_074

トップレベルの `def __pyinto_runtime__():` は特殊なRuntime関数としてASTの段階で切り分け、Construct Modelへ含めず、Frontendは本体のPython構文を正規化・検証しない。マジック関数は同期・引数なし・デコレータなし・単一定義とし、同名のクラス・async関数・直接代入、重複定義、引数つき/装飾つき定義を拒否する。PythonFrontend.parse単体でもこの定義を除外する。モデル化する通常部分は従来のFrontend受理条件に従い、特殊関数の除外はその他の型・名前解決の制約を緩和しない。

title: Runtimeマジック関数の静的分離

level: MUST

## FRT_075

Kind の語は `from pyinto.kinds.<公開面>.<段> import 語 [as 別名]` で import した名前だけを静的に認識する。公開面は `datatypes` / `memory` / `declarations`、段は `general` / `detailed` であり、各モジュールは決まった語だけを提供する。そのモジュールに属さない語、`import pyinto.kinds...` 形式、`pyinto.kinds` やその公開面からの import、組み込み型名との衝突、重複した別名は拒否する。型の位置では、`Wide[X]` / `Narrow[X]` / `Unsigned[X]` を `X`、`Size` / `Index` / `Byte` / `Int[N]` / `UInt[N]` / `CodeUnit[N]` / `Pointer[T]` / `Enum[T]` を `int`、`Float[N]` / `Decimal[N]` を `float`、`Char` を `str`、`Array[T, N]` と `Buffer[T]` を `list[T]`、`Function[[...], R]` を `Callable[[...], R]`、`Void` / `Nil` / `Null` を `None`、`Ref[T]` / `Owned[T]` / `Shared[T]` を `T` と同じ Python 側の形状として扱い、記述どおりのラベルを付ける。サイズと長さは正の整数リテラルだけを受理し、範囲は Host では決めない。引数の個数・種類が語の書式に合わない注釈は拒否する。

title: Kindのimportと型注釈

level: MUST

## FRT_076

値の位置の `Void` / `Nil` / `Null` は `NoneAlias` に正規化し、ラベルを持つ宣言・引数への代入と、ラベルを持つ値との `==` / `!=` 比較（`NoneAliasComparison`）にだけ使える。`Pointer.address(x)` は変数名そのものの引数だけを受理して `AddressOf`、`Pointer.load(p)` は `Pointer[T]` 型の値から `PointerLoad`、文としての `Pointer.store(p, v)` は `PointerStore` に正規化する。キーワード・展開引数、個数の誤り、未知の操作名、式の中の `Pointer.store` は拒否する。型の語彙を値として使うことも拒否する。

title: None別名の値とポインタ操作の正規化

level: MUST

## FRT_077

`Ref[T]` 型の変数の初期化子と、`Ref[T]` 型の仮引数へ渡す引数（既定値を含む）は、マップ済みオブジェクト以外の変数名そのもの（`Reference`）でなければならない。式やリテラルは拒否する。宣言後の代入は通常の代入規則に従い、`Ref` の書き込み・再束縛の意味は Target が決める。

title: Ref型の束縛位置における変数名の要求

level: MUST

## FRT_078

モジュールレベルのクラス定義では、登録済みのクラスデコレータ1個に加えて、`pyinto.kinds.declarations.detailed` の `@Interface` / `@MixIn` / `@Implements(...)` を任意の順で付けられる。`Interface` と `MixIn` は引数なし、`Implements` は同じモジュールでそれより前に定義したクラス名を1個以上とる。自身の名前、未定義・後方のクラス、キーワード引数、同じ語彙の重複、型の語彙のデコレータ使用は拒否する。これらはクラスの受理条件（明示的な `__init__`、単一継承等）を緩和しない。

title: Kindのクラスデコレータ

level: MUST

## FRT_079

Interface Mapping のマップ済みオブジェクトは `クラス.variant()` の引数なしの呼出でだけ生成する。位置引数・キーワード引数・展開引数は拒否し、数値の範囲やサイズをマップ済みオブジェクトの形状として受け取らない。登録するコンストラクタは `(Symbol) -> Construct` とする。

title: マップ済みオブジェクトの引数なしコンストラクタ

level: MUST

## FRT_080

`Memory.new(T, value)` / `Memory.new_buffer(T, length, value)` / `Memory.length(h)` / `Memory.borrow(h)` は値として、`Memory.release(h)` / `Memory.resize(h, length)` / `Memory.copy(destination, source)` / `Memory.fill(h, value)` は文として正規化する。`T` は型注釈と同じ規則で読む。`resize` の対象は変数名そのものでなければならない。値の型が合わない、所有のラベルや `Buffer` のラベルがない、長さが整数でない、引数の個数が違う、キーワード・展開引数、未知の操作名、式の中の文の操作、型としての `Memory` の使用は拒否する。`Memory.new` の結果は `Owned` のラベルを持つが、`Shared` として宣言した変数へも代入でき、所有の種類は宣言から読む。

title: 動的メモリの操作の正規化

level: MUST

## FRT_081

トップレベルの `__pyinto_runtime__` を定義したSourceは、`pyinto.kinds` とその下のモジュールを import できない。`__pyinto_runtime__` があるSourceは実行され得るが、Kindの語彙は変換のための記述であり実行を想定しないためである。`from ... import` と `import` のどちらの形も、`__pyinto_runtime__` の本体の中の import も対象とする。この規則はSource自体の矛盾を示すものであり、選択したTargetの目的に関係なく、`PythonFrontend.parse` でも `convert()` でも、Pythonを実行する前に `UnsupportedPython` で拒否する。`__pyinto_runtime__` のないSourceでのKindの利用は従来どおりである。

title: Runtime関数とKindの併用禁止

level: MUST
