<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/status/canonical.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# pyinto 開発状況

開発段階の実装済み事実と未実装事項。

## 開発段階

バージョン `0.0.1`、開発段階 Alpha。Template / Slot モデルへの基盤刷新を実装済み。後方互換性は保証しない。

## 現在の公開・開発構成（第50回）

- **Host（`pyinto`）**：Foundation・Language Interface・Python Source Adapter・
  Surfaceの役割を同一パッケージで提供する。`convert()` / `realize()`は
  Realization登録を明示して利用し、特定Targetを暗黙選択しない。
- **成果物提出**：Target Packは`pack_dispatch`で`composition`または
  `structural`を宣言でき、生成処理単位で`pack_session`の新しい状態を作る。
  HostはRealizer呼出を管理し、最終成果物はSessionの`finish()`から受け取り
  形式を変換せず返す。`composition`はTemplate/Slotの連鎖を維持し、
  TextArtifactSessionが既存の文字列生成を担う。`structural`は全Constructを
  `parts()`順の深さ優先先行順で訪問し、`visit`実装がTarget状態を操作する。
  非テキスト（dictやbytes）を返せる。`pack_semantics`で意味保存（既定）
  と意味射影を区別し、射影では実行意味の`supports`照合を要求しない。
  `pack_unhandled`は既定の`error`か`traverse`を宣言でき、後者はStructuralで
  意味射影を選んだTargetだけが使用できる。未登録RealizerのConstructを
  訪問せずに子へ進めるが、Admission未登録のModelは必ず拒否する。
  RealizationのvariantはConstructの `variant_domain()` で既知の有限候補を
  登録時に検証し、存在しないvariantを拒否する。省略は従来のdefault指定で、
  Structural射影Targetにおける複数variant/開いた定義域では省略できない。
  `variant @= "*"` は任意variantの明示選択となり、個別指定が優先する。
  Dynamic IntrinsicCallのように候補が開いているものは完全列挙しない。
  個別射影の正しさを検査する包括的な契約体系、成果物への意味モード情報の
  自動埋め込みは未実装。
- **開発用C Realizer**：`tests/support/c_realizer/`に移管した
  非公開の参照実装。`from tests.support.c_realizer import c_bindings`は
  開発・テスト環境専用であり、別配布Wheelや自動選択は提供しない。
  公開HostはC実装への依存を持たない。
- **開発用Python Realizer**：`tests/support/python_realizer/`に配置し、
  非公開のテスト補助としてのみ使用する。HostのWheelには含めず、
  型注釈保持や完全往復変換を保証しない。
- **Interface Mapping**：`pyinto.interface_mapping`の既存登録APIで
  外部Python APIをConstructへ正規化する。`pyinto.interfaces` は
  Language/Builtinsの既存Constructを同一性維持で再公開する薄い窓口。
  外部Interfaceの自動探索・登録、CLI、Target自動発見、Bundle組成は未実装。
- **Model型情報**：`PortType`、`ValueKind.PORT_OBJECT`、`port:`は現行識別名。
  型同一性の検討なしにInterfaceへ機械的に置換しない。
- **管理単位**：配布対象はHost Wheelのみ。C/Python参照Realizerは
  共に`tests/support/`で管理し、ホストの公開API境界と意味保存を検証する。
  意味保存の検証は登録契約の照合に加えて実行テストを要する。

## 実装済み

- 第46回・自作関数の型付き可変長引数：トップレベル `def f(*items: T)`
  と固定引数を伴う同形式を `FunctionSignature.variadic_parameter` と
  実行時同種可変長 `TupleType` の型情報で保持。0個以上の静的な位置引数を
  既存 `FunctionCall` に順序付きで保持し、関数本体で `len`、`sum`、
  `for` に利用できる。固定長Tupleとは区別し、固定長Tuple値の整合する
  同種可変長Tuple型への代入は受理。定義と呼出にそれぞれ新しい
  `function.variadic.tuple_binding` / `call.variadic.tuple_binding` の
  Admission義務を要求。動的 `*` 展開・関数値化・メソッドやネスト関数の
  varargs・**kwargsは未対応。C Targetの実現規則は追加しない。
- 第45回・`global` スカラー複合代入：第44回の明示globalによる
  モジュール変数への代入を、既存int/floatのAugAssignにも拡張。
  元のSymbol同一性とAugAssignの順序・再束縛契約を保持する。
  関数ローカル名の事前収集にAugAssignを追加し、明示globalなしで
  `counter += 1` が外側の同名Symbolへ誤解決する問題を修正。
  ModelとTargetの実現規則は変更せず、未対応のC Targetは拒否する。
- 第44回・限定的な `global`：トップレベルの型付き関数で、docstringに
  続く先頭の `global` が、関数定義以前に型付き初期化された
  モジュール変数だけを指定できる。単純再代入と読み取りを元の
  `Symbol(scope=())` を参照する `Assign` / `Reference` として正規化。
  後方/未知/Port名、引数衝突、型付き再宣言、ネスト関数/メソッド、
  途中や制御本体内の `global`、反復対象を拒否。
  Modelに `global` Constructは追加せず、C Targetの関数実現も未追加。
- 第43回・再帰的な型表記：`type_name @= callable` は
  `(shape, spell)` を受け取る。`spell(inner_type)` は現在のTargetに
  登録された規則を再利用し、入れ子のlist・dict・tuple・Callableと
  Port型からの参照にも対応する。未登録の内側型、不正な型名、
  同じ具体型への再帰を明示的に拒否し、独立した要求間に処理状態を残さない。
  固定型名指定は従来どおりで、旧1引数Selectorの互換呼出はしない。
- 第42回・型Slot／配置の整理：型表記Selectorは`ValueType`の完全な
  複合形状を受け取り、Port型は`PortType`を維持する。戻り値型を
  `FunctionDefinition`の`${return_type}`に公開し、`FieldDefinition`等の
  既存型Slotと同じComposer経路で描画できる。Model由来のタプル型Slotは
  `separators @= {"parameters": ", "}`のように区切りを指定できる。
  未対応型、不正Slot、区切り指定の誤りを明示的に拒否する。
- 外部関数Interface MappingのShikumi親子宣言：
  `@maps(function)`を親クラスに、`@signature(...)`を入れ子クラスに、
  `factory @= ...`を子クラスに指定し、
  `InterfaceMappingRegistry.from_declarations()`から既存の関数Mappingへ変換する。
  関数オブジェクトの定義元を使用し、動的な関数呼出・自動登録はしない。
  既存の署名照合とFrontendの受理・拒否範囲は維持する。
  クラス/メソッドMappingは現段階では対象外で、
  再エクスポートなど定義元と公開名が異なるケースは別途設計する。
- 外部Interface関数Mappingの静的可変長位置引数・複数署名：
  `InterfaceVariadicParameter` により任意個数の明示された位置引数を
  順序付きでModel factoryへ渡せる。同一完全修飾名の異なる署名を
  追加登録可能。引数式は候補数によらず一度だけ正規化し、一意に
  合致する署名だけを選ぶ。登録時の重複・呼出時の曖昧さ・候補なし、
  動的展開と意味を保存できない引数再順序化は拒否する。
  署名の優先順位を登録順から推測しない。Target別実装は増やさない。
- 外部Interface関数Mappingの引数正規化：`InterfaceParameter`で
  静的な名前付きパラメータ、型、不変リテラルの既定値を定義できる。
  位置・キーワード・混在形式を同じ宣言順へ束縛し、未知名・重複・
  個数不足・型不一致・展開引数を拒否する。並べ替えで副作用の
  評価順序が変わる場合は未対応として明示拒否する。外部Classや
  Method Mapping、Target Realizationは変更していない。
- Python Source Adapterの絶対import拡張：`import module`・`as`別名・
  多段モジュール・`from package import submodule`を既存Interface Mappingへ
  静的に接続。標準/外部ライブラリの別による分岐は設けず、未登録名や
  名前衝突を拒否する。Importはモジュールを読み込まず、ModelとTargetの
  Realizationには変更しない。相対・動的・スコープ内importは未対応。
- 公開面再設計・第5工程：HostのShikumi宣言は `@realizes(element)` と
  `@naming` の二種類だけとし、C Target・開発用Python Realizer・テスト・
  例示コードも単一の宣言体系に統一。互換用の情報型・代入記述器・登録分岐・
  命名マーカーの代入処理は持たない。未宣言や重複対象は拒否する。
  一般の外部直接Call要素と`accepts`の型要素化は引き続き未実装。
- 公開面再設計・第4工程：C Targetの全22宣言と、非公開の開発用Python
  Realizerの全26宣言を`@realizes(element)` / `@naming`へ移行。
  Constructのvariant、`print`の直接Call、基本型の表記、命名規則、
  契約支持・拒否動作を維持。
- 公開面再設計・第3工程：引数なしマーカー `@naming` を追加。
  `@realizes(element)` と同じ宣言クラスでは併用できない。
  Target内の命名ポリシー重複、`requirement_line` の不正Slot、
  Namingへの `supports` 誤宣言は拒否する。
- 公開面再設計・第2工程：Shikumiの `@realizes(element)` を追加。
  `lang.While` などのConstructクラス、`builtin.PrintCall`（従来の
  キー `print` に対応する直接Call）、`vt.Integer` などのValueKind、
  PortTypeインスタンスを、既存Registryの各登録経路へ接続する。
  `builtin.PrintValues` は別Constructとして維持。登録の重複、
  無効な要素、契約未対応、Slot不正などを明示拒否する。
  C Targetと開発用Python Realizerの移行は第4工程で完了。
  Frontendの変換範囲は不変。

- 公開面整理・第1工程：HostのModel側公開窓口として
  `pyinto.interfaces.language`、`pyinto.interfaces.builtins`、
  `pyinto.model.value_types`を新設。実体は既存ConstructとValueKindの
  再エクスポートで、型同一性・Admission・Realization選択は維持。
- 第36回移行工程8：2配布物の独立Wheel・クリーンインストール、
  HostからCへの逆向きimport禁止、公開APIの明示的Realization選択、
  Cコード生成・gcc実行と未実装Constructの明示拒否を検証。
  開発テスト用のContrace契約資産はソースに保持したまま
  Host Wheelから除外。監査の回帰テストを追加し、Modelの意味契約・
  Frontend受理条件・Realizationの実装範囲には変更を加えていない。
  論理的な分離の工程は一巡したが、Gitリポジトリの物理的分割は未実施。

- 第36回移行工程6：従来の公開Python Target実装を
  `tests/support/python_realizer/` へ移し、非公開の開発用Realizerとして保持。
  HostのWheelには含まず、Surfaceから暗黙に利用せず、既存の
  Model→Python実現・実行回帰テストのためだけに明示使用する。
  Construct・Admission・Realizationの実現範囲は変更しない。
  型注釈を保持する往復変換を保証するものではなく、今後の検証課題とする。

- 第36回移行工程5：C Target Implementationを同一リポジトリの
  `targets/c/src/pyinto_target_c/` に配置。Hostの配布パッケージと
  C Targetの配布パッケージを分け、HostからCへの互換再エクスポートを削除。
  `pyinto_target_c.c_bindings()`を明示して変換し、Hostからの
  逆向きimportを静的テストで検査する。物理的なリポジトリ分割は未実施。
  開発用Python Realizerの整理は工程6で実施した。

- 第36回移行工程4c：Python側の外部API対応付けを `pyinto.interface_mapping`、
  `InterfaceMappingRegistry`、`InterfaceFunctionMapping`、
  `InterfaceClassMapping`、`InterfaceMethodMapping`、
  `InterfaceMappingNormalizer` に名称整理。変換APIとFrontendの引数は
  `interface_mappings=`。Model内部の `PortType`、`PORT_OBJECT` と型キーは
  型同一性を保持するため今回は維持。既存の受理・拒否条件は不変。


- 第36回移行工程4b：`BindingRegistry` を `RealizationRegistry` へ、
  `pyinto.bindings` を `pyinto.realizations` へ変更。出力Layout用モジュールは
  `pyinto.realizations.layout`、Surface引数は `realizations=` とする。
  Target factory (`c_bindings()` 等)とPort関連名は第36回時点では維持。
  言語構造の受理条件、Admissionの要求と明示拒否は変更しない。

- 第36回移行工程4a：既定契約台帳は`LANGUAGE_ADMISSION`、
  基準台帳の検査は`AdmissionRegistry.require_baseline()`に改名済み。

- 第36回移行工程3：配布名・Python import 名前空間を `pyinto` に変更。
  既存の `convert()` / `realize()`、Admission、Binding、Port、Target Pack の
  API名と意味契約を工程3時点で維持し、C/Python Target を同梱する。
  その後の工程4a/4bで上記のAPI名を整理した。物理的なTarget分割は未実施。

- Model表現能力拡充第12回（第35回作業）：制御本体
  （if/else・while/else・for/else・with）に限り、初期値付きの
  型注釈宣言を既存Initializeとして受理（FRT_071）。宣言した名は
  同じ本体の後続文・入れ子本体でのみ使用し、分岐外や別の節からは
  参照させない。Pythonにブロックスコープを導入せず、宣言Symbolの
  所属は元の関数/モジュールのまま。新規束縛をlambdaで捕捉する
  形式、Port宣言・再束縛、try直下での新規宣言は引き続き拒否する。
  既存ConstructとTarget Packの実現範囲を維持したまま、
  新規記法の拡張をここで一区切りとする。次工程はPython Pack中心の
  Realization・意味保存の検証であり、C Packは必要時の重点検証に使う。

- Model表現能力拡充第11回（第34回作業）：forの単一新規変数を
  `IterationEntry.introduces_binding` で区別。range / str / 型付きList /
  同一要素型の非空Tupleからだけ導入型を確定し、空反復の架空の初期化は
  作らない。新規導入の参照は本体内に限定し、else・後続への参照は
  解析せず拒否。新規導入形には `iteration.binding.introduced` を
  Admissionで要求し、Python/C標準Packは未対応のまま。

- Model表現能力拡充第10回（第33回作業）：型付きListとStringの
  スライスを `SliceValue` で保持（CST_072 / FRT_069）。開始・終了・
  ステップの省略と明示値を区別し、対象から境界までの一回評価と順序、
  Pythonの負添字・範囲調整・0ステップ例外、Listの浅い外側コピーと
  StringのUnicode単位を意味契約として登録した。辞書・Tupleの
  スライスやスライス代入は拒否し、Python/C標準Packは未実装のまま。

- Model表現能力拡充第9回（第32回作業）：`Membership` を
  `list[T]` の要素、`dict[K,V]` のキーの所属判定へ追加。左から右への
  評価順、種類ごとのPython所属規則と否定を独立契約とし、従来の
  `StringContains` は維持する（CST_071 / FRT_068）。既知の型を検証し、
  動的な包含プロトコル・Tuple所属・比較チェーン内の所属は拒否。
  Python/C標準Packへのレシピはまだ追加しない。

- Model表現能力拡充第8回（第31回作業）：固定長Tupleの既宣言名への
  `UnpackAssign` を追加（CST_070 / FRT_067）。右辺を一度評価して
  全位置の値を確定した後、左から順に対象を更新する契約を保持する。
  入れ子・スター付き対象、新規宣言、Port再束縛は未対応。
  Python/C標準PackのRealizationは追加していない。

- Model表現能力拡充第7回（第30回作業）：`FormattedString` で書式なしf-stringの
  断片と評価順を保持し、埋め込み式は登録済みの型付きstr IntrinsicCallで
  文字列化する。0個・複数・異種スカラー引数のprintを `PrintValues` で
  表現し、全引数評価後の出力・空白区切り・改行を契約化。
  単一文字列printは従来のCallを維持（CST_069 / FRT_066）。
  format spec/!r/!a/出力先・改行指定・任意オブジェクト出力は未対応。
  新しいTarget Packレシピは追加していない。

- Model表現能力拡充第6回（第29回作業）：標準提供者表
  `standard_intrinsics()` に `str/int/float` の無引数と型付き
  `int/float/str/bool` からの一引数変換15署名、および
  `str.upper/str.lower` を登録（CST_068 / FRT_065）。
  既定PythonFrontendが標準表を参照するが、明示intrinsics指定で
  置き換え可能。変換ごとの意味契約と静的な型・個数の拒否を検証。
  入力値の評価・フォーマット推論・型昇格は行わず、例外やUnicodeの
  規則は実行時契約として保持する。Python/C標準Packへの
  Intrinsicレシピ追加は今回行っていない。

- Model表現能力拡充第5回（第28回作業）：`IntrinsicRegistry` に
  同じ操作系列の複数静的シグネチャを登録できるようにした。
  `IntrinsicTypeVar` / `IntrinsicListType` はIntrinsic署名内に限定し、
  `list[T].append(T)` や `str(int)` / `str(float)` の区別を既知型から
  一意に解決する（CST_067 / FRT_064）。重複署名、複数候補適合、
  型不一致、未束縛の戻り値型変数を拒否。選択済みの具体シグネチャと
  署名固有obligationsをModelへ保持し、Realizationは同じ系列のまま
  supportsを照合する。Noneを返す基本メソッドの式文にも対応。
  汎用型推論、暗黙変換、Python/C Packの実装は加えていない。

- Model表現能力拡充第4回（第27回作業）：提供者が定義する
  `IntrinsicDefinition` と `IntrinsicRegistry`、それに対応する
  `IntrinsicCall` を追加（CST_066 / FRT_063）。Receiverの有無、
  引数・結果の再帰的なValueType、操作識別子・追加の意味義務を
  ModelとFrontendの独立した構造として保持する。Receiver評価・引数評価の
  一回性と順序をConstruct提供側Admissionで要求し、単純文字列Template
  のSlot重複・欠落・並び替えを拒否する。今回の登録表は既定では空で、
  テストでは利用者登録の型付き操作だけを正規化する。既存組込み・
  Python/C標準Target Packの受理範囲は変更せず、一般の動的
  メソッド解決、型推論、オーバーロード、Targetの実現は未対応。
- Model表現能力拡充第3回（第26回作業）：厳密なint同士の真の除算を
  floatを返す `IntegerTrueDivision` に保持し、整数 `Arithmetic` に
  `&` / `|` / `^` / `<<` / `>>`、`IntegerUnary` に `~` を追加。
  既存 `AugAssign` の整数複合代入にもこれらのビット演算を追加した。
  Pythonの任意精度・負数の符号拡張・負シフト回数の例外、整数から
  floatへの変換、左から右の評価順をModelの契約として明示し、
  Construct提供側Admissionで照合する（CST_065 / FRT_062）。
  C/Python標準Packは未対応の演算を引き続き拒否する。
- Model表現能力拡充第2回（第25回作業）：型付きint/floatの単純名・フィールドへの
  `AugAssign` と、同一型int/float/strの `ComparisonChain` を追加。
  左辺格納先の一回評価・右辺の後続評価と再束縛、比較中間値の一回評価・
  短絡をModelの契約として保持（CST_063〜064 / FRT_060〜061）。
  提供者側Admission規則とフィールド・非フィールド監査へ明示登録し、
  Targetの実現方法は固定しない。標準C/Python Packのレシピは未追加。
- Model表現能力拡充第1回（第24回作業）：`Pass` を明示的な無操作文として
  Construct / Frontend に追加（CST_062 / FRT_059）。モジュール・関数・
  メソッド・クラス宣言の先頭docstringを静的な文字列メタデータとして
  Modelに保持し、非先頭文字列式の拒否は維持した。限定dataclassと
  コンストラクタの初期化規則も維持。AdmissionRegistryと監査台帳に
  Passと追加フィールドを登録し、Target Packの実現範囲は拡張しない。
- 第23回：型付き二項式の被演算子評価順、Port Callの明示実引数順、
  FunctionValueCallのcallee先行をConstruct提供側の受理規則へ追加（CMP_020）。
  直接文字列TemplateでValue Slotの欠落・重複・順序変更を拒否。
  C標準Comparisonは評価順を保証できない複合式を保守的に拒否し、
  Python標準Comparisonは言語固有の順序契約に対応する。
  TemplatePlanや一般のTarget実行意味は自動的には検証できない。
- 第22回：キーワード引数・既定値・dataclass・lambda・符号付き定数の
  正規化をModel/Realizationの責務境界で点検し、Python正本の
  Realization境界監査文書に採用済み契約と保留判断を記録。
  dataclassと明示的な__init__のModel一致、引数束縛・評価順・省略の
  情報保持、lambda識別子の衝突回避と動的意味の拒否を回帰検証。
  既存仕様・Frontendの受理範囲・Target Packは変更しない。
  第23回の評価順・Slot監査は別工程として実施済み。
- 第21回：C/Python標準PackのForに対するbreak/continueと
  正常完了else、PythonのWithに対する入場・退出・例外時の挙動を
  Construct提供側の受理規則に追加（CMP_019）。対象Target Packに
  supportsを宣言し、欠落時には描画前に拒否。C/Pythonの実行試験を
  追加した。Comparison等の評価順序は未保護として継続監査。
- 第20回：Construct の受理規則を Target から切り離し、Core と外部
  Port 提供者の `AdmissionDeclaration` に登録。未登録の具体Construct
  （継承した派生クラスを含む）は、Templateで利用されない子も含めて
  合成前に拒否。`realize(admission=...)` と
  `convert(interface_mappings=...)` の提供者契約の受け渡しを実装（CMP_018）。
  既存の未保護 `pending` 意味契約は残り、Realization の受理宣言は
  生成コードの意味保存を保証しない。
- 型アノテーション付き変数定義の必須化。型不整合やアノテーションなしの
  新規束縛は Frontend が拒否。再代入は既存の明示型を利用。
- Python AST → `Program` / `Block` / `Branch` / `While` / `For` / `With` /
  `Break` / `Continue` / `Range` / `IterationEntry` / `ContextEntry` / `Reference` /
  `Literal` / `Initialize` / `Assign` / `AugAssign` / `Comparison` / `ComparisonChain` / `Call` /
  `ExpressionStatement` / `Arithmetic` / `IntegerUnary` /
  `BooleanOperation` / `BooleanNot` / `BooleanLiteral` / `NoneLiteral` /
  `ConditionalExpression` / `Length` / `Absolute` / `Extremum` /
  `IntegerSum` / `BooleanAggregate` /
  `FunctionDefinition` / `FunctionCall` /
  `FunctionValueCall` / `LambdaValue` / `Return` / `Parameter` / `FunctionSignature` /
  `TupleValue` / `TupleElement` / `Raise` / `ExceptHandler` / `Try` への正規化。
- Construct から `emit()` と `Snippets`（AAA+Cleanup）を撤去。
  各 Construct の名前付き子構造 `parts()` と構造の `variant()` を提供。
- Target Pack は Shikumi 宣言による単一 `template` または動的な
  テンプレート選択 `render` を提供。余剰/不足 Hole、重複定義などを拒否。
- Composer は再帰的に Template / Slot を接続する。子の早期文字列化なし。
  Renderer が行単位 Slot のインデントと最終文字列出力を処理。
- Binding 選択時の `EmitContext` から、合成の根、担当 Construct、親、
  祖先、経路を読み取り可能にした。元の Construct は変更しない規約とし、
  生成状態は別に保持する。Slot の初出順で子を合成し、合成要求ごとに
  ヘッダと補助名の生成状態を初期化する。
- `while` を条件式 Construct と本体 Block、任意の `else` Block として正規化。
  C / Python 両 Binding がループと正常終了時の Block を実現する。
  `Break` と `Continue` は独立 Construct であり、C と Python の
  ループ Binding が `break` による中断と正常終了時の `else` を実現。
- `for` の反復入口を `IterationEntry`、反復元を Value として正規化。
  C Binding は整数 `range` に対応し、Python Binding は反復構造を保持。
  反復中の `break` / `continue`、`else` を C/Python 両方で検証。
- `with` は順序付き `ContextEntry` と本体 Block を正規化。
  Python Binding は `with` を実現。C Binding 未登録の場合は
  Construct を拒否せず C 変換時に明確なエラーを返す。
- ヘッダなどの要求は子の構成時に収集し、完成後の最終レンダリングで配置。
- C Target Pack と Python Target Pack の差し替え。
- 外部関数 Port (`DeviceIsReady`) とインスタンス Port
  (`ManualMemoryRegion`) の明示登録・Target Binding。
- インスタンス Port の `release()` を独立した明示的操作として扱い、
  自動 Cleanup しない。
- `a: ManualMemoryRegion = ...; b: ManualMemoryRegion = a` の
  単純な別名宣言と、宣言済み制約の Target 型解決を実装。
  対応 Binding がない型表現は拒否する。
- 第30段階後の内部整理として、`constructs.py` を型・基底・型規則・値・
  コレクション・制御・演算・関数・クラスの各モジュールへ分離した。
  `frontend.py` は PythonFrontend の統括 `parser.py` と、状態を明示的に
  受け取る型注釈処理、デコレーター識別登録、共通診断に分離し始めた。
  登録されたデコレーターでも正規化規則を未実装の場合は拒否する。
  既存の意味契約と Realization の受理範囲は変更していない（FRT_058）。
- 第30段階後のモジュール整理第2回として、PythonFrontend の解析入口を
  `frontend/parser.py` に限定し、クラス、関数（lambda と名前解決を含む）、
  文と例外、式、外部 Port の正規化規則を個別モジュールへ移動した。
  各領域の内部操作は `FrontendOperations` の型付きシグネチャを共有し、
  宣言・レキシカルスコープ、クラス、制御フローに関する可変解析状態を
  `ParseContext` に分け、parse ごとに作り直す。
  これは実装の配置と解析状態の寿命の整理であり、受理・拒否条件、
  Model、Realization の契約を変更するものではない。
  領域間の相互呼出は現在も存在し、独立した正規化コンポーネントへの
  完全な責務分離は今後の検討事項とする。
- 第30段階後の基盤整理第19回では、束縛済み直接呼出5種の
  Realization受理規則に、2つ以上の明示実引数の順序保証
  `call.arguments.left_to_right` を追加。仮引数への並べ替えは
  `call.arguments.reordered` に分離し、既定値補完を評価数から除外
  （CMP_017）。ModelはTarget言語の評価規則を保持しない。
  同時に、脱糖／責務境界、Construct提供者による契約登録、
  標準Packのpending解消の順序を監査正本で計画した。
  これら後続項目はまだ実装済みではない。
- 第30段階後の基盤整理第18回では、Realization の必須契約抽出を
  `AdmissionRule` の宣言群へ整理し、対象Construct・`guard`フィールド・
  要求契約を型付きで対応付けた。追加のルールは既存の基本規則を
  置き換えずにBindingRegistryへ合成でき、具体名と開いた契約ファミリーを
  扱う（CMP_016）。監査台帳のフィールド分類・非フィールド意味義務と
  実装済みルールの照合をテストで自動検証する。将来候補の名前付き基本操作、
  AugAssign、比較チェーンは仮モデルと受理宣言による試験に留め、
  実際のConstructやFrontend対応は追加していない。未保護のfinally、
  短絡、クロージャー環境寿命などは明示的に`pending`として残る。
- 第30段階後の基盤整理第17回では、反復元を `range`、`str`、`list`、
  型付きタプル（および Model の一般 Iterable）として分類し、
  `For` と `IterationEntry` で Realization の `supports` による
  対応形式の照合を追加（CMP_015）。Frontend は非反復可能値、
  型不一致と FRT_025 で拒否する辞書反復を明示的に拒否（FRT_003）。
  C Pack は range のみ、Python Pack は構文上の反復展開を登録。
  Target の意味保存の自動証明までは実装していない。
- 第30段階後の基盤整理第14回では、Realization の受理条件強化に先立ち、
  Construct の dataclass フィールド全域を Python 正本の監査台帳で
  分類した。意味情報の単なる公開と、受理条件としての強制を区別し、
  呼出順序・省略・dispatch、反復元、短絡評価、finally、クロージャー等の
  未保護契約を非規範的な日本語監査文書へ記録した。
  台帳と実装のドリフトを検出するテスト、可変長の名前付き基本操作を想定した
  レシピ検索の設計プローブを追加した。Realization の適用条件、Model、
  Frontend の意味契約・受理範囲は今回まだ変更していない。
- 第30段階後の基盤整理第13回では、クラス・メソッド・継承・Receiver の
  正規化を `ClassNormalizer` へ移行した。`ClassServices` に型注釈・
  関数署名収集/本体組立・引数束縛・名前解決・値解析などの他領域への
  依存だけを明示する。クラスの効果登録と `ParseContext` は解析単位で共有し、
  `PythonFrontend` は必要なクラス操作を委譲する。残存していた
  `ClassNormalization` Mixin と内部スタブ基底 `FrontendOperations` を撤去。
  `ImportNormalizer`、Port・式・文・関数・クラス正規化器はすべて
  独立オブジェクトとして構成される。既存の意味契約と Target Realization
  の受理範囲は変更していない。ただし各 Services は一部
  `PythonFrontend` の委譲入口を通じて相互参照し、循環する操作依存の
  完全な解消を意味しない。
- 第30段階後の基盤整理第12回では、関数宣言・呼出・lambda・レキシカル
  名前解決を `FunctionNormalizer` として Frontend の Mixin 継承から
  独立させた。関数領域が必要とする型注釈・メソッド種別・Block・値の
  正規化操作を `FunctionServices` に限定し、`ParseContext` と
  `DecoratorRegistry` は解析単位で明示的に共有する。クラス・式・文からの
  関数操作は `PythonFrontend` の委譲入口を経由する。旧
  `FunctionNormalization` Mixin を撤去し、Contrace 対象とテストを更新した。
  当時はクラス領域に Mixin が残っていた。既存の名前解決・Callable・評価順・受理拒否条件、Model と
  Realization の契約は変更していない。
- 第30段階後の基盤整理第11回では、文・制御フロー・例外の正規化を
  `StatementNormalizer` として Frontend の多重継承から独立させた。
  `ParseContext` と `InterfaceMappingNormalizer` を解析単位で受け取り、関数・クラス・式など
  他領域の操作は `StatementServices` に明示した依存先へ委譲する。
  `PythonFrontend` は文と Block の解析入口のみを委譲し、例外構造の組立てと
  再帰的な Block の解析を文コンポーネント内部へ閉じ込めた。
  旧 `StatementNormalization` Mixin は撤去し、Contrace の実装対象と
  構造検証テストを更新した。関数・クラス領域には Mixin が残っており、
  Frontend 全体の依存関係の独立化は未完了。既存の受理・拒否条件、
  Model および Realization の契約は変更していない。
- 第30段階後の基盤整理第10回では、式の正規化を Frontend の多重継承から
  独立した `ExpressionNormalizer` に移した。式だけが必要とする
  名前解決・関数呼出・クラス関連の操作を `ExpressionServices` という
  小さな型付き依存契約に限定し、`ParseContext` と Port 正規化器を
  解析単位で明示的に共有する。`PythonFrontend` の式操作は
  独立コンポーネントへの委譲とし、状態の再生成を単一の
  `_reset_parse_state` に集約した。これにより式領域は
  `FrontendOperations` の全メソッドを継承しない。
  ほかの関数・クラス・文の領域では Mixin 構成が残り、完全な独立化
  は完了していない。既存の式の受理・拒否、Model、および
  Realization の契約に変更は加えていない。
- 第30段階後の基盤整理第9回では、外部 Port の正規化を
  `PythonFrontend` の多重継承から独立した `InterfaceMappingNormalizer` へ移し、
  `ParseContext`、登録済み Port と、値・スコープ参照に必要な
  最小限のコールバックだけを明示的に渡す構造にした。
  同じ import 群での型名・Port・デコレーターの名前束縛を
  `ImportNormalizer` に分離し、デコレーター登録機構との接続を
  Frontend の入口から切り離した。parse ごとに Port 正規化器と
  import 正規化器を再構築する。既存の受理・拒否条件と Model、
  Realization の契約は変更していない。ほかの正規化領域の Mixin と
  `FrontendOperations` の依存関係は継続して整理する。
- 第30段階後の基盤整理第3回では、`Symbol` の型を分散した kind / 複合型形状
  の複数保存フィールドから `type: ValueType | PortType | None` の単一の
  保存フィールドへ変更した。通常の値型・Port の宣言・組み込み専用名を
  明確に区別し、kind と複合型形状は読み取りプロパティとして導出する。
  関数署名の Callable 型生成、Frontend の引数期待型、クラスの
  override 署名検査で宣言の ValueType を直接参照するようにした。
  既存の受理・拒否条件と Realization の契約は変更していない。
  FunctionSignature の戻り型や Python 型注釈の多値返却、
  型互換性の全域統一、Realization の受理契約の機械的検査は継続課題である。
- 第30段階後の基盤整理第4回では、`FunctionSignature.return_type` を単一の
  `ValueType` に集約し、呼出値の戻り型と Callable 型生成、override 署名
  の照合で同じ型オブジェクトを直接利用するようにした。
  Frontend の型注釈正規化も表記と `ValueType` の組を返し、登録済み Port
  クラスの注釈のみ通常の ValueType と分離した。旧戻り型の分散フィールドと
  7要素タプルは撤去した。既存の受理条件・意味契約および Realization は
  変更していない。Value 基底や型互換性の規則統合、Model の戻り値検証、
  Realization 適用条件の強化は今後の課題である。
- 第30段階後の基盤整理第5回では、構造的 `Value` の戻り型・要素型を
  `value_type` という単一の読み取り契約へ集約し、形状別の重複した
  転送プロパティを削除した。スカラー値は従来の種別から型を構築する。
  Port 参照の特殊な型区分は維持している。
  `type_rules.assignable(expected, actual)` に、従来の最上位型と
  公称インスタンスの派生型代入規則を明示し、間接関数値呼出も直接呼出と
  同じ規則にそろえた。Callable・型付きコレクションの形状は厳密一致の
  ままとし、Model の新しい型推論や Target Realization は導入しない。
  関数本体の戻り値検証、Frontend 全体の型条件の集約、Realization の
  明示的な適用条件は引き続き今後の課題である。
- 第30段階後の基盤整理第6回では、`FunctionDefinition` が自身の
  `Block` に属する明示 `Return` の型を Model 構築時に検証するようにした。
  分岐、反復、`With`、`Try` の各子 Block を静的に確認するが、入れ子の
  関数や式内の lambda の戻り値を外側に混同せず、全経路での return の
  到達性は推論しない。Frontend の通常関数・lambda の戻り値照合では
  共通の `assignable` を利用し、元のソース位置付き診断と `None` の
  限定記法、既存の値型の受理範囲を維持した。Target Realization の
  適用条件と Frontend の状態管理の整理は引き続き後続課題とする。
- 第30段階後の基盤整理第7回では、Frontend のインスタンス参照候補を
  判定のために正規化してから再度正規化する経路を改め、生成済み Value を
  フィールド参照・更新、通常メソッド呼出、関数値フィールドの呼出へ渡す。
  式に含まれる lambda の識別子が二重に消費されないことを回帰テストで
  確認した。名前付き関数と lambda に重複していたレキシカルスコープ・
  呼出し中の解析状態の退避復元を `ParseContext.callable_scope` にまとめ、
  例外による正規化失敗時にも親の状態を復元する。メソッド固有の
  フィールド初期化状態は名前付き関数でのみ切り替え、lambda は既存の
  解析コンテキストを引き継ぐ。新しい型推論・Python 実行時解析や
  Realization の実現規則は追加していない。
- 第30段階後の基盤整理第8回では、Frontend のデコレーター識別と
  明示的な効果正規化ハンドラーを分離した。組込み staticmethod / classmethod
  / dataclass を登録済みハンドラーへ移し、class / method / function の
  宣言位置それぞれで外部の静的な正規化規則を登録できるようにした。
  class 計画は宣言収集と構築の間で再利用し、関数の後処理ハンドラーには
  同一署名の FunctionDefinition の返却を要求する。未登録・未実装効果、
  デコレーター呼出やスタックは拒否し、Python のデコレーター実行と
  Target の実現は行わない（FRT_058）。
- 第30段階後の基盤整理第16回では、直接呼出5種の複合意味契約を
  同時に検証するテストを追加し、Realizationの宣言欠落がrenderやヘッダ
  変更より前に拒否されることを確認した。文字列Templateに対しては、
  呼出元で明示された実引数Slotの重複・省略・ソース順からの並べ替えを
  合成時に拒否する検査を追加（CMP_014）。既定値省略を含む呼出と
  TemplatePlanによる評価順保持のTarget側展開をPython実行で確認した。
  ただしTemplatePlanの任意の内容やdispatch実装の正しさは、
  `supports`宣言やSlot検査から一般的に証明できない。
- 第30段階後の基盤整理第15回で Realization エントリーに明示的な
  `supports` 契約名の登録と受理時の機械的な照合を追加。関数・
  コンストラクタ・メソッド等の直接呼出における束縛済み引数、
  ソース評価順の変更、省略された既定値、VIRTUAL/SUPER と探索起点、
  実行時のクラス Receiver 同一性を必須条件として照合する。
  未宣言はコード生成前（コールバック/ヘッダ変更前）に拒否する。
  Model 側への Realization 依存追加や Target の実現方式の決定はしない。
  この宣言自体は生成コードの意味保存を保証せず、既存の
  C/Python Pack に未実装の新しい Call レシピを追加していない。
- Shikumi-Contrace 契約と pytest で変換・未対応時の失敗・
  C コンパイル / 実行 / Python 実行を検証。
- 日本語文書を Shikumi-Devdoc の正本 Python から生成。
- `shikumi-devdoc` の Specification 正本によって、Construct、Frontend、
  Composition の現行実装契約を個別の安定IDで文書化し、INDEXと生成・整合性検査を追加。
- SDD 第7段階で整数算術 `+` / `-` / `*` / `//` / `%`、整数単項
  `+` / `-`、Boolean `and` / `or` / `not` を Model と Frontend に追加。
  演算の順序・ネスト・短絡性を保持し、Python AST の式を評価しない。
  演算子と型の Model 構築時検証、未対応演算子の診断を追加
  （CST_015〜016 / FRT_007〜008）。Target Pack の新規実現規則は追加していない。
- SDD 第25段階として静的に解決済みの直接関数・通常/基底メソッド・インスタンス生成に
  名前付き実引数を追加。評価順と仮引数への束縛順を独立して保持し、
  未知名・重複・展開・欠損を拒否（CST_056 / FRT_048〜049）。
  第25段階時点では Callable 型の間接呼出とデフォルト値は未対応だった。
- SDD 第27〜29段階で、`@staticmethod` を Receiver のない静的メソッド、
  `@classmethod` を実行時クラス Receiver を保持するメソッドとして限定的に
  正規化。`ClassMethodCall` / `ClassReceiverCreation` は単一継承時の
  クラス同一性を維持し、Realization へ構造的に渡す。
  `@dataclass` は明示 import・型付き静的フィールドから従来の
  `ClassDefinition` / `FunctionDefinition(__init__)` / `FieldInitialize`
  を生成し、既存の限定デフォルト値・キーワード引数の契約を再利用する。
  汎用 Decorator・一般の descriptor・dataclass の完全な実行時効果は
  今回採用していない（CST_058〜060 / FRT_052〜055）。
- SDD 第30段階として `lambda` を式 `LambdaValue` に正規化。
  明示的な `Callable` 期待型から無注釈パラメータを型付けし、単一式を
  既存 `FunctionDefinition` / `Return` に保存。入れ子関数と同じ
  レキシカル束縛/捕捉を維持し、新しい Closure Construct は追加しない。
  型情報が不足する場合や可変長/既定引数は拒否する（CST_061 / FRT_056〜057）。
  対応する Target Realization はまだ未登録で、既存 `with` 等は変更しない。
- SDD 第26段階で型付き関数・インスタンスメソッド・初期化メソッドに
  限定された不変スカラーデフォルト引数を追加。末尾の引数の省略を静的に補完し、
  `omitted_arguments` と `supplied_evaluation_arguments` で明示実引数の順序と
  省略補完を区別する（CST_057 / FRT_050〜051）。
  一般的な Python の定義時の式評価・可変デフォルト共有は要求しない。
  関数値間接呼出の省略指定は対象外。Target Realization は未登録。
- SDD 第8段階としてトップレベルの型付き関数定義・引数・戻り値・関数呼出と
  関数ローカルスコープを Model / Frontend に追加。署名を先行収集し、再帰・
  前方参照の導線を保持する。戻り値種別 `None` を区別し、未対応構文や
  引数不整合は明示的に拒否する（CST_017〜018 / FRT_009〜010）。
  新たな Function* / Return Realization はまだ提供しない。
- SDD 第9段階として、既存の `FunctionDefinition` と `Block` による
  任意深度の直接入れ子関数を Python Frontend で受理。階層的な
  レキシカル名前解決により親関数の値参照、直接関数呼出、同階層の
  前方参照と再帰呼出に対応。`FunctionSignature.scope` と
  `Symbol.scope` に宣言の所有経路を保持して同名宣言を区別する
  （CST_019 / FRT_011〜012）。専用の Closure Construct は導入しない。
  関数 Realization はまだ提供しない。
- SDD 第23段階で整数集約 `sum`（list[int]・固定 int タプル・range）、
  Boolean 短絡集約 `any` / `all`（list[bool]・固定 bool タプル）を
  `IntegerSum` / `BooleanAggregate` の型付き Value として追加した。
  集約の対象式・明示開始値・順序と短絡は Model の契約に保持し、
  型なし空リスト、一般 truthiness、任意 iterable は拒否する。
  これらの Realization は未登録。
- SDD 第22段階で `len` / `abs` / `min` / `max` を
  `Length` / `Absolute` / `Extremum` の型付き Value として正規化。
  `len` は文字列・固定長タプル・可変リスト・可変辞書だけを対象とし、
  `abs` および2引数以上の `min` / `max` は整数型に限定。
  評価時点・一回評価・順序を契約とし Target Realization は未登録。
- SDD 第10段階として `ValueKind.FUNCTION`、再帰的な `ValueType` /
  `CallableType`、関数宣言ごとの `value_symbol` を追加。明示 import した
  `typing.Callable` 型注釈と関数値の参照、型付き変数での保持・再代入、
  関数引数・戻り値としての受け渡しを Model / Frontend に追加した。
  直接 `FunctionCall` が関数型を返す場合も型形状を保持する。
  第10段階時点では関数値を介する間接呼出と関数値 Realization は未対応だった
  （CST_020〜021 / FRT_013〜014）。既存 `with` 等は変更しない。
- SDD 第11段階で `FunctionValueCall` を新設し、`Callable` 型変数・引数
  および関数型を返す式を介した間接呼出を正規化できるようにした。
  関数値自体が callee 子要素となり、位置引数の個数・型を構築時に検証。
  callee の一回評価と引数の順序を契約化し、関数型の戻り値も伝播する。
  既存 `FunctionCall` と `with` の意味契約は変更していない。
  関数値・間接呼出の Realization は未登録（CST_022 / FRT_015〜016）。
- SDD 第12段階で新しい Construct を追加せず、読み取り専用の
  `pyinto.analysis.lexical_captures()` により、関数本体から直接の
  外側レキシカル参照を初出順で導出できることを確認した。
  自己再帰・モジュール参照・子関数の本体を直接捕捉から除外し、
  関数宣言値への参照や入れ子関数の直接呼出にも対応する。
  ただし実行ごとの環境の生成・共有・寿命・推移的保持は検証しない
  （CST_023〜024 / FRT_017）。Realization は未登録のままとする。
- SDD 第13段階で固定長の型付きタプルを新たに採用。
  `TupleType` と再帰的 `ValueType`、`TupleValue` と `TupleElement` で
  `(a, b)` / `tuple[int, str]` / `t[0]` を保持する。空・ネストしたタプル、
  関数の仮引数・戻り値、`Callable` との組み合わせも可能。
  要素ごとの型・位置は静的に検証し、値式は事前評価しない。
  Realization は未登録（CST_025〜026 / FRT_018〜019）。
  既存 `with` の設計判断は変更していない。
- SDD 第14段階で `Raise` / `ExceptHandler` / `Try` を Model に追加。
  組込みの `ValueError` / `TypeError` / `RuntimeError` に対する
  明示的な送出と型別捕捉、`try` / `except` / `else` / `finally` の
  順序付き制御構造を Python Frontend で正規化。送出メッセージは
  文字列 Value のみ受理し、実行せず構造として保持する。
  例外伝播と `finally` の全退出経路の優先順位を Realization の契約とし、
  Model は対象コードの実行機構を決めない（CST_027〜029 / FRT_020〜021）。
  Target Realization は未登録。既存 `with` の規則には変更がない。
- SDD 第15段階で単一要素型を持つ `list[T]` と `ListType`、
  `ListValue` / `ListElement` / `ListElementAssign` を追加。
  空・ネストしたリスト、引数・戻り値・Callable・タプルとの合成、
  整数式による要素参照・型付き要素更新を Frontend で正規化。
  別名と外側スコープのリスト変更も既存の参照関係を維持する。
  要素数変更・スライス・内包表記は未対応。
  Target Realization は未登録（CST_030〜031 / FRT_022〜023）。
  既存 `with` その他の規則には変更がない。
- SDD 第16段階として `dict[K, V]`（キー型は `int` または `str`）と
  `DictType` / `DictEntry` / `DictValue` / `DictElement` / `DictElementAssign`
  を追加。挿入順序と式の一回評価、キー不在の読み取りによる失敗、
  既存キーの更新と新規キーの追加、別名参照の可変共有を契約化。
  空辞書は期待される明示型がある場合のみ受理。関数・Callable・
  リスト・タプル・ネストした辞書と合成できる。
  Target Realization は未登録（CST_032〜033 / FRT_024〜025）。
  既存 `with`・タプル・リスト・例外処理の意味契約は変更していない。
- SDD 第17段階として公称インスタンス型 `InstanceType` / `ValueKind.INSTANCE`、
  `ClassSignature` / `ClassDefinition`、型付き `FieldDefinition`、
  `InstanceCreation` / `FieldInitialize` / `FieldRead` / `FieldWrite` /
  `MethodCall` を追加。通常の FunctionDefinition をメソッドに再利用し、
  第一引数の受取手を `ParameterRole.RECEIVER` として明示的に識別する。
  静的に確定した `__init__` 内フィールド、受取手・別名参照、
  メソッド・公称型の整合性を Model / Frontend で検証する。
  （第17段階当時は）継承、特殊メソッド一般、動的属性、デコレーターは未対応。
  Target Realization は未登録（CST_034〜036 / FRT_026〜028）。
  既存 `with` その他の意味論は変更しない。
- SDD 第18段階として静的な単一継承を導入し、`InstanceType.base` /
  `ClassSignature.base` と階層に沿ったフィールド・メソッド探索を追加。
  型付きの基底クラス参照と `MethodDispatch.VIRTUAL`、レキシカルな
  `MethodDispatch.SUPER` を区別する。派生型の型整合、オーバーライド
  署名の検証、明示的な一回の基底 `__init__` 呼出を実装。
  Target Realization は未追加（CST_037〜039 / FRT_029〜031）。
- SDD 第19段階で既存の単一継承・クラス・複合値・関数値・クロージャー
  の合成を検証。型付きリスト/辞書/タプル要素、関数やメソッドの戻り値から
  得たインスタンスを、`MethodCall(VIRTUAL)` の Receiver として保持する。
  `Callable` 型インスタンスフィールド呼出は `FieldRead` と
  `FunctionValueCall` を組み合わせ、通常のメソッド呼出と区別。
  新しい Construct クラスや Target Realization は導入しない
  （CST_040〜041 / FRT_032〜034）。既存 `with` 等の契約は変更しない。
- SDD 第20段階では、既存の Construct 全体の基本表現能力を
  Model / Frontend / Realization ごとに棚卸しした。Boolean 定数値、
  一般の None 値、条件式、コレクション操作などの候補を、
  現行の受理と拒否に基づき優先分類した。
  `devdocs/reviews/phase20_construct_capability_audit_ja.md` に
  非規範的な判断材料をまとめ、37件の独立した受理・拒否プローブを追加。
  既存の Construct / Frontend / Realization の実装と意味論は変更せず、
  次の新機能の採用判断は保留した。
- SDD 第21段階で `BooleanLiteral` / `NoneLiteral` /
  `ConditionalExpression` を Model / Frontend に追加した。
  Boolean 定数は整数とは別の Value とし、一般的な `None` 値は
  `object` / `Any` の明示型付き値として利用可能にした。
  条件式は両枝の型を明示的に検証し、実行時は選択した枝のみ評価する。
  `Optional` / `Union` の自動型推論は導入していない。
  `Literal` の int/str 契約、`-> None` の Return 契約、
  既存 `with` の意味契約は変更していない
  （CST_042〜044 / FRT_035〜038）。Realization は未登録。
- SDD 第24段階で `float` 明示型・有限リテラル・型付き浮動演算と比較、
  文字列の連結・繰返し・辞書順比較・部分文字列包含・Unicode 添字を
  Model と Frontend に追加（CST_050〜055 / FRT_045〜047）。
  混合数値型への暗黙変換・文字列スライス・ユーザー定義の特殊メソッドは採用せず、
  既存の数値・文字列構造の意味論は変更しない。新規 Target Realization は未登録。
- SDD 第6段階として `Construct.HOLES` を必須 Slot ではなく
  静的に公開可能な Model 要素名として明確化。`accepts_part_name()`
  を追加し、`With.entryN` のような動的要素名も宣言検証可能にした。
  `Comparison` / `Initialize` / `Assign` / `Branch` / `While` は
  不正な型・演算子を生成時点で拒否するよう変更（CST_013〜014 / CMP_012）。
- SDD 第5段階として Model 境界を追加監査。`Program.HOLES` から
  出力専用 `requirements` を除外し、Shikumi 規定体が Program だけに
  当該 Slot を許すよう変更。`Literal` は構築時点で int / str のみを
  厳密に受理する。Model 単独構築・複数 Target 間の再利用・非変異と
  不正な Slot / 型の拒否を独立テストで検証（CST_010〜012 / CMP_011）。
- SDD 第4段階として `For.parts()` の range 固有 `target/start/stop/step`
  投影を廃止し、`For` には `entry/body/otherwise` のみを保持。
  C の range 実現に必要な Slot は Realization の `TemplatePlan` が供給し、
  Composer は Model を書き換えず再帰的に接続する。CST_009 / CMP_010 と
  新たな境界・拒否テストを追加。
- SDD 第3段階として `Program.to_source()` / `to_c()` を撤去し、
  Model とは独立した `pyinto.convert()` と `pyinto.realize()` を公開。
  Target は Registry から決定し、Core は標準 C Pack を暗黙選択しない。
  内部的な Shikumi-Contrace の ProgramPort も CompositionPort に移行。
  仕様 CVT_001〜003、CMP_009 と回帰テストを追加。
- SDD 第2段階として基本 Construct の `parts()` と配置専用 Layout 型を分離。
  名前は `Identifier`、型参照は `Symbol`、Block は `tuple`、
  `With` エントリーは順序付き動的 Slot として公開する。
  出力要求の Slot は Composer 側で補完し、Python Target が `with` の区切りを決める。
- 公開プロジェクト名と Python パッケージを `henkan` へ変更。
  新概念の Model / Interface / Realization は用語集で定義し、旧 Port / Binding API は現段階では維持。

## 未実装・制限

- 第16回のSlot検査は文字列Templateのみを対象とする。
  動的TemplatePlanを使用するTargetの実際の意味保存には個別の
  実行テストが必要で、任意のRealizationを機械的に証明するものではない。
- 第15回では直接呼出5種に関する受理条件の照合を実装したが、
  監査したすべての非フィールド意味契約への強制適用は **未実装**。
  反復、短絡、クロージャー寿命、`finally` などの条件や、
  宣言された Target 実現の実際の正しさを検証する仕組みは残る。
  `supports` の確認は実現規則の自己宣言に基づくものであり、
  不正な自己宣言を単独では発見できない。
- Frontend の Mixin は撤去済みだが、複数の Services が統括オブジェクトの
  委譲入口を通じて相互呼出する依存は残る。必要性と複雑さを考慮して
  今後の改善を判断する。デコレーターの登録・効果ハンドラーは導入したが、現行の型付き返値
  （ClassDecorationPlan / MethodKind / 同署名 FunctionDefinition）以外の
  任意の Construct / Interface への置換や、複数デコレーターの合成は
  今後の個別設計を要する。登録した名前だけでは使用可能にならない。
- ループ内部での新規変数定義や Port の再束縛。
- C Target での一般的な `for` イテラブル、`with` の入退出・例外抑制、
  C での Python 例外クラス（`range` のステップ 0 等）の再現。
- `for` / `with` に関する AST の全構文（分配代入など）。
- 新たな算術・論理演算 Construct の Target Realization（C / Python とも未登録）。
- 第24段階の浮動小数点演算・比較と文字列操作の Target Realization。
  浮動小数点精度を要求する追加 Interface、暗黙の数値型昇格、文字列スライス、
  実行時の Unicode 添字表現への Target 側の対応も未実装。

  `//` / `%` の Python 規則や `and` / `or` の短絡性を
  Target に委譲するため、対応 Realization なしでは明示的に失敗する。
- 浮動小数点、一般的な `/` / `**` / ビット演算、真偽値変換、
  一般的な truthiness、可変オブジェクトへの複合代入、任意型・同一性・所属演算を含む比較チェーン。
- 一般的な Python 組み込み全体の受理（`sum`、`zip`、`enumerate` 等）、
  任意オブジェクトの `__len__` / `__abs__`、Iterable の min/max、
  `key=` / `default=` と新基本操作の Target Realization。
- `None` を持ち得る一般的な `Optional` / `Union` と型付きコレクション要素、
  Boolean/None/条件式の Target Realization。
- 可変長タプル型の実行時添字・負の添字・スライス、
  要素代入・アンパック、タプルの Target Realization。タプルへのアクセスは非負の静的整数添字のみ。
  リストの長さ変更メソッド・スライス・内包表記と Target Realization は未対応。
- 任意例外型・例外インスタンスの一般的な値、`except ... as`、
  裸の `except`、`raise` の再送出と原因連鎖、`except*`、
  例外メッセージの多引数・非文字列形式、例外処理 Construct の
  Target Realization。対応する Realization がなければ明示的に拒否する。
- すべての Python AST や Python 実行時意味論の等価な変換。
- 複数の可能な Port 参照や分岐を跨ぐ Port 再束縛、
  関数の高度な引数形式・未採用の一般デコレータ・関数値の Target Realization・
  クロージャーの逸出後の捕捉変数の寿命の実現・
  限定範囲外の `global`・一般的な Python スコープ（nonlocal 等）、
  コレクション経由の参照の一般化。関数内の制御構造での def も未対応。
- 関数の完全な戻り値経路の解析、関数定義・呼出・return の
  Target Realization。現在のモデルは静的な導線を保持するが、
  Target 上での成立を保証しない。
- 多重継承・一般的な MRO・動的な基底クラス変更、descriptor、メタクラス、クラス属性、
  プロパティ、選択的に採用した3種以外のデコレーター、クラスオブジェクトの第一級値、
  動的属性変更、動的なキーワード引数・展開引数、各特殊メソッドの一般的実行機構。
  新規クラス関連 Construct の Target Realization。
- `typing.Any` / `object` に対する C Target の汎用的な表現。
- ターゲット固有の式準備処理を任意の実行位置へ再配置する仕組み。
- メモリ確保失敗、解放漏れ、二重解放、解放後使用の静的保証。
- Python Port と他言語ライブラリの全体的な意味的等価性保証。
- Target Pack の外部配布、自動探索、Target Binding API の安定化。
- 公開向け英語文書。

未対応項目は自動的に推測して実装せず、必要な構造・契約・Binding が
明示できた場合のみ拡張する。

## 次の検証

SDD 第1段階で現行仕様を作成し、第2段階で `parts()` の Layout 補助型依存を外し、
第3段階で変換入口を Model の外へ移した。
第4段階で `For.parts()` の range 展開責務を C Realization に移した。
第5段階では Program の出力専用 Slot と Literal の値域を Model の
責務から分離・明確化し、Model 非変異の回帰テストを追加した。
第6段階では HOLES / parts() の責務を区別し、一部 Model の
整合性検証を構築時点に移した。旧 HOLES 名は互換性のため維持。
第7段階では型が明示された整数・論理演算を Model と Frontend に追加した。
第8段階ではトップレベルの型付き関数署名・定義・呼出・return と
ローカルスコープを Construct と Frontend に追加した。
第9段階では既存の関数 Construct の再帰構造を利用し、
静的なレキシカルスコープを Frontend に追加した。入れ子の深さごとに
Construct を増設せず、元の Model の意味論も見直していない。
第10段階では関数値の型情報と参照を既存 `Reference` と型付き
変数・引数・戻り値へ追加した。第11段階では新しい `FunctionValueCall`
により関数値からの直接的な位置引数呼出および多段呼出を正規化した。
第12段階では新たな Closure Construct を導入せず、静的な直接捕捉の
導出可能性を独立した解析関数と検証テストで確認した。
第13段階では固定長タプル値と静的な位置参照を Model と Frontend に追加した。
第14段階では限定した組込み例外と `try` / `except` / `else` / `finally` を
Model と Frontend に追加した。第15段階では型付き可変リスト、
第16段階では型付き可変辞書を追加した。第17段階では静的な
公称インスタンスクラスと明示的なメソッド受取手の Model / Frontend を
追加した。第18段階では静的な単一継承、明示的な super、
型付き仮想ディスパッチとオーバーライド契約を Model と Frontend に追加した。
第19段階でクラスと複合値・関数値・クロージャーの
合成を検証し、関数型フィールドの間接呼出と複合式を Receiver とする
仮想呼出を Frontend に追加した。
第20段階では、Construct 全体の受理能力と不足候補を、
Model と Realization の区別を保って独立レビューに整理した。
新しい Construct を追加せず、現行の受理・拒否プローブを回帰テスト化した。
第21段階では優先候補の Boolean 定数・None 値・条件式を
限定した意味で Model / Frontend に追加した。
第23段階では `sum`、`any` / `all` を要素型が静的に確定した
集約操作として Model / Frontend に追加し、短絡・開始値と評価順序を契約にした。
第22段階では基本組み込み操作の `len`（文字列・固定長タプル・
型付き可変リスト・辞書）、整数 `abs`・`min`・`max` を
`Length` / `Absolute` / `Extremum` として追加した。
残る組み込み操作についても、**今後追加する意味に限って**
仕様採用の是非と実現契約を個別検討する。
関数や式に対応する Realization は未登録のため、変換時に明示的に失敗する。
既存の `with` 等の設計判断は維持し、新たな機能に
限り意味の採用範囲を検討する。
第24段階では、浮動小数点の明示型と型付き四則演算・比較、文字列の
連結・繰返し・比較・包含・添字を追加し、新規意味のみを採用した。
モデル化と Target 実現可能性を区別し、既存 Construct の意味契約は維持する。
Interface の本格導入、Realization API の改名、CLI と Cartridge 選択は
未着手であり、現行仕様へ混ぜない。
