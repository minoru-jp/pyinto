<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/reviews/realization_boundary.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# henkan Realization 受理条件監査（第14回）

開発用の非規範的な監査記録。既存 Specification を置換しない。

## 監査範囲と分類の限界

第13回成果物を基準に、現存する Construct の全 dataclass フィールドを
`FIELD_ROLES` に主たる役割で明示分類した。`tests/test_realization_boundary_audit_iteration14.py`
が全クラス・全フィールドとの差分を検出する。分類は監査の入口であり、
複数の役割を兼ねるフィールドについても代表的な1役割を記録する。
意味保存を証明するものでも Realization の受理検証を実装したものでもない。

- `part`：`parts()` に直接または `Identifier` / 番号付き子として現れる。
- `select`：現行の Call 名前検索、または `variant()` に利用される。
- `render`：葉値の出力コールバックで読む必要がある。
- `context`：宣言・型・所有関係として原 Construct に保持され、Realization
  コールバックが読める。ただし読んだことを保証しない。
- `guard`：Template に黙って無視されうる意味上の差異。
  第15回で直接呼出5種の一部の契約を照合できるようになったが、
  残る全契約を実装済みと判断しない。

`part` に現れる要素であっても、Template は未参照の子を合成しない
（CMP_003 / CMP_007）。そのため `part` であるだけでは意味保存を保証しない。
また、短絡評価・finally・反復対象の型・環境寿命など、個別フィールドの
分類だけでは見つからない契約を `SEMANTIC_OBLIGATIONS` に別記した。

## 優先度の高い未保護契約

現行の登録選択は `(type(node), node.variant())`、登録済み Port Call
では `callee.name` を用いる。`EmitContext` から Model 全体に到達できるが、
静的 Template に意味条件を読ませる義務はない。

| 代表領域 | 観測した不足 | 次工程で必要な確認 |
|---|---|---|
| MethodCall | dispatch / lookup_start は同一 default variant | SUPER と VIRTUAL の区別の強制 |
| 直接呼出5種類 | evaluation_order / omitted_arguments は規則選択に不使用 | 副作用式・省略済み実引数の安全な扱い |
| IterationEntry / For | 反復元 Value の型は読めるが適用検証が一貫しない | 対応反復形式を宣言・拒否する仕組み |
| Try / With / LambdaValue | parts はあるが制御フロー・環境寿命は Slot だけで保証不能 | 一般的な推論を行わない明示的な能力宣言 |
| BooleanOperation / BooleanAggregate | 短絡条件が個別フィールドの欠落として検出されない | フィールド監査と別建ての契約監査 |

第14回時点の PythonFrontend の `for` 分岐は対象名の既宣言のみを確認し、
`for k in n`（n:int）や辞書反復などの誤受理があった。
第17回で反復可能な型・要素型の検査を追加し、FRT_025 との不整合を修正。
また `For` と `IterationEntry` に反復種類別の受理契約を導入した（CMP_015）。

`parts()` に `arguments` を番号付き展開しても、現行のソース順と
仮引数順の違いは自動的に解消されない。逆に、そのために既存の
キーワード引数やデフォルト引数の意味論を変更することもしない。

## 将来の基本操作・記法の設計検証

まだ実装しない将来拡張の机上テストとして、次を想定する。

1. 名前付き基本操作：`list.append` / `str.upper` のような増加する
   `(receiver type, operation name)` をレシピ識別可能であること。
   入力側のメソッド記法を理由に Interface と決めつけない。
   ただし実際の `IntrinsicCall` 導入、既存 `Length` 等の統合は保留。
2. `AugAssign`：再束縛と同一オブジェクト更新の差異、左辺の一回評価を
   実現規則側で宣言できること。単なる二項演算＋代入へは還元しない。
3. 比較チェーン：中間式を一度だけ評価し、短絡する意味契約を
   個数・演算子列の組合せ爆発なしに宣言できること。

これらは新しい Construct でも Python 構文対応でもない。受理機構の
設計制約として使い、名前の自由集合を全件列挙するような仕組み、
あるいはすべての義務を variant へ押し込む仕組みを避ける。

## 第18回：監査の継続性と未保護契約の明示

第18回では、監査台帳の `guard` 付きフィールドを、`constructs.admission`
の `ADMISSION_RULES` が宣言する `guarded_fields` と全件照合する。
ポリシーは適用 Construct、観測対象フィールド、取り得る契約識別子
（具体名またはキーを増やせる `.*` ファミリー）、抽出関数を明示する。
必須契約は Realization の `supports` と照合され、未宣言なら拒否する。

さらに `SEMANTIC_OBLIGATIONS` の全項目に対し、
`SEMANTIC_ADMISSION_STATUS` で `admitted:<rule>`、`frontend:<spec>`、
`pending:<reason>` のいずれかを明記した。テストは対応する rule の存在、
監査した Construct への適用、未登録フィールドや意味義務の検出、
及び実際の契約抽出を検証する。`pending` は完了扱いにせず、今後の
受理強化の作業候補として残す。フィールドを `context` と宣言するか
`guard` と宣言するかの判断自体は、引き続き人間の設計レビューが必要。

将来の記法 `IntrinsicCall` / `AugAssign` / 比較チェーンは、
製品用Constructを増やさずテスト用の仮構造として確認した。
型と名前の開いたキー、対象評価の一回性、短絡と中間式一回評価の
契約キーを、variantの組合せを増やすことなく表現可能。
これは将来の実現規則の正しさや、現時点でのFrontend受理を意味しない。

## 統合修正計画と第19回責務境界の現状監査

**第19回からの統合計画（第18回終了後の責務境界点検＋レビュー反映）**

| 工程 | 対象 | 完了判定 | 第20回時点 |
|---|---|---|---|
| 19 | 順序契約の適用範囲を修正。位置引数も保護し、並べ替えと区別 | 未宣言のTarget規則が描画前に拒否される | **実装済み**（直接束縛呼出5種） |
| 20 | 契約定義の所有者をTargetではなくConstruct提供側へ移す。Port提供者の明示登録も追加 | 未登録Constructと「義務なし宣言」の違いを扱い、未知を拒否 | **実装済み**（CMP_018） |
| 21 | 標準C/Python Packの`For`・`With`等の活性化済みpendingを抽出して解消 | 契約を宣言したTarget上の実行テストと未保護Pack検出 | **実装済み**（For / With。Comparisonの順序義務は第23回へ明示保留） |
| 22 | 脱糖と責務境界の総点検（キーワード引数・デフォルト値・dataclass・lambda等） | 採用した限定契約とTarget実現戦略の区別、変更判断と試験 | **監査・回帰試験完了**。意味契約は変更せず、既定値等の再設計判断は保留 |
| 23 | 未保護の評価順（演算式、関数値・Port呼出）とSlot未使用の扱いを個別に設計 | 安全な拒否または根拠付きの適用規則、監査の更新 | **主要対象は実装済み**。任意TemplatePlan・全子Slot網羅の一般証明は対象外 |

**第19回の責務境界の確認**：
- `FunctionCall`等の`evaluation_order`は仮引数への束縛位置と
  元ソースの評価順を記録する既存Model情報。`left_to_right`を
  Realizationが要求するのはTargetの言語仕様をModelに注入するため
  ではない。例えばCで引数評価が未規定であることはC側の判断である。
- `frontend/functions.py`ではデフォルト引数を呼出側へ補完し、
  `omitted_arguments`として区別する。仮想メソッドのデフォルト一致制約
  との結合は別途仕様判断を要する。今回、この契約を撤去しない。
- `frontend/decorator_effects.py`では限定された`@dataclass`から
  `ast.FunctionDef(__init__)`を合成して既存解析へ流す。
  これはTargetの生成コードではないが、Model直接組立との比較余地がある。
- `frontend/functions.py`のlambdaは`__henkan_lambda_N`という内部名を
  生成する。実際のTarget識別子として固定すべきかは要検討。
- キーワード引数は型付きの束縛順と記述上の評価順を区別する。
  その正規化自体と、Targetの引数評価・配置方針は異なる責務。
- 基本操作の`IntrinsicCall`や`list.append`をConstructとする
  可能性は開いた名前空間で試験済みだが、製品実装・既存`Length`
  などの置換は**今回行わない**。

現在の監査台帳`SEMANTIC_OBLIGATIONS`は**非網羅的**であり、
追加した二項演算・Port Call等の評価順もpendingに明示した。
`supports`とSlot検査はTargetの意味保存の証明ではない。
特にC系の引数並びのテキスト上の順番を実行時の評価順と同一視しない。

## 第20回：提供者契約とRealizationの所有境界

**第20回の確認結果**：

- `AdmissionRule` / `AdmissionDeclaration` / `AdmissionRegistry` は
  Target固有コードから独立した `henkan.admission` に移設した。
  Coreの67種類の具体型は `constructs.admission` に明示宣言し、
  テストで第14回の監査対象型集合との相違を検出する。
- `BindingRegistry` の `additional_admission_rules` は廃止。
  外部のConstructは提供者がPortRegistryの `admission_declarations`
  に登録し、`realize(admission=...)` または `convert(ports=...)`
  で選択する。Target Packの作者が独自の契約を静かに追加する
  経路は設けない。Coreの登録の削除・置換も拒否する。
- 受理規則のない明示宣言は許すが、登録がないConstruct型を
  同じ扱いにはしない。Composerは `parts()` の子を事前監査し、
  文字列Templateが省いた子の未登録も検出する。
  ただし全子の実現や意味保存は別途検証が必要である。
- メモリPortの値域と代入・解放の契約は提供者の定義側へ置いた。
  C Packの `supports` と照合し、ターゲットによる未宣言契約の
  自動無視を防ぐ。外部の正規化範囲は拡張しない。
- `pending`契約を今回強制するものではない。第21回では
  実際に標準Packが出力する For / With の未保護契約を優先して
  具体的な実現・実行試験を整える。

**第21回の実績**：Core定義側の `for_control_flow` と
`with_context_management` で For の break/continue・正常完了 else、
With の入場・退出・例外時の振る舞いを機械的な必須契約にした。
C/Python標準Packは対応する実現規則だけに `supports` を付与し、
欠落するレシピは描画前に拒否する。
Cのrangeループの break/continue/else を実コンパイル・実行で、
Pythonのforとwithを実行時のイベント列で検証する。
監査対象のうち標準Packで生きている残存 `pending` は
`Comparison.operand_evaluation_sequence` である。今回これを
対応済みや免除済みと偽らず、第23回の演算順序の課題として明示保留する。
標準Packで実現しない `pending` は引き続き監査台帳に残る。

## 第22回：脱糖処理と責務境界の総点検

**第22回：脱糖処理と責務境界の総点検（設計判断と再現試験）**

今回は既存の限定意味契約を改訂しない。以下は実装に照らした
*現行契約の確認* と *将来の変更に必要な判断* であって、
新たなTarget Realizationの提供や脱糖方式の変更を宣言するものではない。
`tests/test_desugaring_boundary_iteration22.py` に回帰プローブを追加した。

| 領域 | 現行の処理と残る情報 | 判断（第22回） |
|---|---|---|
| キーワード実引数 | Frontendが静的な仮引数名へ束縛し、`arguments`は宣言順、`evaluation_order`は入力上の評価順を保持。Realizationに順序と束縛を要求 | **維持**。名前解決と契約の保持はFrontend/Modelの責務。Target側の配置・一時変数生成はRealizationの責務。前者を廃止すると静的束縛が失われる |
| 既定値 | 末尾の不変スカラーだけを許し、呼出側に補完し`omitted_arguments`で明示引数との差を保持。仮想メソッドのoverrideでは既定値一致が必須 | **仕様判断を保留**。補完位置はModelに残るが、override制約は補完方式の帰結。将来省略形を保持する表現へ変更するなら、仮想呼出のデフォルト選択を先に仕様化し、CST_057/FRT_050〜051等を明示改訂する |
| dataclass | `decorator_effects.dataclass_plan()`で限定された型付きフィールドから`ast.FunctionDef(__init__)`を合成し、既存の関数/クラス正規化へ通す | **当面維持**。生成ASTはFrontend内部の再利用手段であり、Targetへの生成コードではない。テストでは型付きの明示的`__init__`と同じModelになる。直接Model組立への移行は、重複実装を増やさずに同一の拒否条件を保証できる場合だけ検討 |
| lambda | 明示された`Callable`期待型と既存のFunctionDefinition/Return/静的捕捉を再利用し、衝突しない`__henkan_lambda_N`を宣言識別子として生成 | **維持**。名前はレキシカルな区別のための内部情報であり、Targetの関数名としてそのまま出力する契約ではない。将来Realizationに識別子の変換手段が必要な場合はRealization側で扱う |
| 符号付き数値 | 負号付きスカラー既定値を不変のLiteral/FloatingLiteralへ正規化 | **維持**。静的な値の正規化でありTargetの符号演算生成方式を決定しない |
| 名前付き基本操作 | `Length`などは基本値操作のConstruct。`list.append`は未実装 | **追加は保留**。メソッド記法と関数記法でConstruct/Interfaceを分類せず、採用する型付き操作の意味契約を先に定義する。`IntrinsicCall`の開いた操作名は受理機構の設計プローブのみ |

**第22回の確認境界**

- dataclassと手書きの型付き初期化を比較し、同一Modelを得ることを
  テストした。Modelの等価性は将来の全dataclass機能を保証しない。
- キーワード引数の束縛順と入力評価順、省略した既定値と明示した
  既定値を区別する情報が失われないことを確認した。
- lambdaの内部名が利用者の宣言と衝突しないこと、一般の
  デコレーター実行と可変デフォルトを拒否することを確認した。
- ModelはCの未規定評価順やTarget固有の一時変数方式を知らない。
  `supports`の照合は出力コードの意味保存の証明ではない。
- 第23回予定の `Comparison`、二項演算、関数値呼出、Port Call の
  順序義務、未参照Slotの扱いは**未解決**。今回の監査を理由に
  `SEMANTIC_ADMISSION_STATUS` のpendingをadmittedへ変更しない。

**今後の仕様変更の決定点**：デフォルトの省略表現とoverride規則、
dataclassの合成経路、lambdaのTarget名変換、IntrinsicCallへの
統合はいずれも独立した選択である。スクラッチ段階なので
API互換は要求しないが、既存の限定意味契約は暗黙に改訂しない。

## 第23回：式とPort呼出の評価順とSlot検査

**第23回：残る評価順序義務と単純TemplateのSlot境界**

`Comparison` を含む既存の型付き二項式について、Modelに保持される
被演算子の順序を `evaluation.operands.left_to_right` として
Construct提供側の `AdmissionRule` へ登録した。`Call`（Port）では
引数が2つ以上あるとき、`FunctionValueCall` ではそれに加えて
calleeを実引数より先に評価する義務を登録。Target固有の評価規則や
副作用推論をModelへ持ち込まない。

静的文字列Templateでは、二項式の子Slot / Port Callの全実引数 /
間接呼出のcalleeと実引数が1回ずつ、所定の文字順で現れるかを確認。
ただしTemplatePlanの変換用Slot、一時変数、任意のTarget式について
この機械検査は実行時評価順を証明しない。特にCの比較演算子は左右の
評価順が規定されないため、標準C Packは両辺が単純参照・定数か、
一方が定数の場合に限定し、それ以外は実現を拒否する。将来の
Realizationは適切な一時変数等を用いて別の対応範囲を持てる。

標準PackのComparisonについての第21回の既知のpendingは解消。
ただし、Boolean短絡、例外、alias、捕捉寿命やTarget実行意味などの
未保護項目はpendingのまま残り、今回の変更は全Contractの保護完了を
意味しない。C/Python標準Packが未対応のConstructを追加したわけでもない。

## 第25回：複合代入と比較チェーンの意味契約

**第25回：Model優先の複合代入・比較チェーン**

`AugAssign` は既存の代入と二項式の合成に還元せず、型付き名・フィールドの
格納先一回評価、読取と右辺評価の順序、スカラー再束縛を明示する。
現段階の `mode` は REBIND のみ受理し、破壊的な IN_PLACE や
添字代入は拒否する。`ComparisonChain` は複数比較を二項Comparison
に複製せず、式の一回評価・中間値共有・左から右への短絡を保持する。

提供者側の `augmented_rebinding` / `ordered_comparison_chain` 規則が
Targetから独立した必要契約を列挙し、監査台帳のフィールド分類と
意味義務を機械的に照合する。C/Python標準Packには新規レシピを
登録せず、ConstructとFrontendの受理をRealizationの完成条件にしない。
明示的なsupportsは意味保存の実行証明ではなく、必要になったTarget
について実行テストなどで別途検証する。

## 第26回：整数演算の型と意味契約の拡張

**第26回：整数ビット演算と真の除算の意味契約**

`IntegerTrueDivision` は左右の厳密な整数Valueからfloat結果を得る
構造として `Arithmetic` と区別する。整数の除算式を事前評価したり、
Target固有の除算命令へ書き換えたりしない。ゼロ除算・巨大整数の
変換エラーを含む真の除算の意味を `integer.true_division.python_float`
でRealizationへ要求し、左右順序を既存の `ordered_operands` に委ねる。

`Arithmetic` / `IntegerUnary` と `AugAssign` のビット演算では
`integer.bitwise.unbounded`、シフトでは追加で
`integer.shift.python_counts` を要求する。これは整数幅・負値の
シフト規則が異なるTargetを宣言だけで誤受理させないための意味契約。
どのTargetでどう実現するかの計算・推論はModelに追加しない。
各Concrete Constructを明示登録し、監査台帳の非フィールド義務と
AdmissionRuleとの対応を機械的に確認する。既存のArithmeticの
`python_integer_division_and_modulo` はpendingのまま残す。
Python/C標準Packには新規レシピを登録しないため、Realization
変換は従来どおり未対応として拒否される。

## 第27回：型付き基本操作の提供者側登録

**第27回：型付き基本操作の提供者表とModel表現能力**

`IntrinsicDefinition` は静的なReceiver型・位置引数型・戻り型と
追加の明示的意味義務を提供者側で所有する。`IntrinsicCall` の
定義参照を監査 `guard` とし、型・操作名をTarget側で推測しない。
必須契約は `intrinsic.<型>.<名前>` と各追加の具体的な義務、
Receiverの一回評価と引数より先の評価、引数の一回評価、
複数引数の順序からなる。`intrinsic.*` はConstruct提供者側の
契約名の開いた系列であり、Target Packのsupportsでワイルドカード
を許す趣旨ではない。単純文字列TemplateについてはReceiverと
引数のSlotを1回ずつ出現順に検査するが、Target言語の実行順序や
TemplatePlan全般の意味保存までは証明しない。

フロントエンドは静的型が一致する明示的な提供者登録だけを採用する。
既定カタログを空に保ち、未知のメソッドやPython組込みの振る舞いを
推論せず、既存の専用Constructも残す。同じ操作系列を複数の
実引数型で多重定義する仕組みは未採用であり、重複キーを拒否する。
Python/C標準PackにIntrinsicのRealizationは追加していない。
Model優先の開発であり、Targetごとの実行テストは今後個別に行う。

## 受理条件強化に向けた次工程

第15回で導入した `supports` は Target Pack が対応を明示的に宣言し、
`required_contracts(node)` が検出する未宣言の義務を描画前に拒否する。
既存の `(Construct 型, variant)` / `Call` 名による選択は変更しない。
初期対象は直接呼出5種の束縛済み引数、引数評価順の並び替え、
デフォルト引数省略、および MethodCall の dispatch / lookup_start、
クラス Receiver 同一性である。宣言は意味保存の自動証明ではない。

第16回では、直接呼出5種について、複合契約の未宣言拒否と静的
文字列Templateの引数Slot使用回数・順序を検査した。明示引数の
再評価・省略・ソース順からの並べ替えを検出する。ただし、TemplatePlan
の独自Slot追加やTarget内部の制御フローまで一般検証するものではなく、
関数引数の評価副作用と既定値の適用を個別のPython実行テストで確認した。
`supports`の自己宣言が正しいかを一般に証明する仕組みは今後もない。
第17回：Frontend の反復型検査と、Realization の反復種類別契約照合を実装。
`For` 全体を自前で展開する Realization でも反復形式を明示的に宣言する。
第18回：`ADMISSION_RULES` の各ポリシーが監査上の `guard` フィールドを
網羅することと、非フィールド意味義務の対応状況を自動照合する。
状態は `admitted`（実行前の対応宣言を照合）、`frontend`（入力側での制限）、
`pending`（Realization受理は未保護）に区別する。
`pending` が残っているため、全Constructの意味保存が保証されたわけではない。

`FIELD_ROLES` は引き続き開発時の監査メタデータであり、
Target の実現能力を自動的に宣言する Runtime API ではない。

## 第28回：基本操作の複数シグネチャと型変数

**第28回：Intrinsicの操作系列と型付き署名を分離**

同一の `intrinsic.<owner>.<name>` に複数の型付きシグネチャを
登録できるようにし、重複の禁止単位を操作キーから
(Receiver型パターン、引数型パターン) の組へ移した。
署名固有obligationsにより、例えば整数の文字列表現と
floatの文字列表現を異なる契約としてRealizationへ要求できる。
既存のIntrinsicCallの `definition=guard` は解決済みの具体シグネチャ
を参照し、Admissionの追加規則を不要とする。

`IntrinsicTypeVar` と `IntrinsicListType` は操作宣言に閉じた型パターン。
Frontendは既知Receiverと実引数の型を照合するだけで、一般的な
型推論・オーバーロード順位付け・副作用解析は行わない。複数候補の
どれも実際に適用できるなら曖昧として拒否する。候補ごとに
Receiverや引数式を重複正規化しない。None戻りのメソッドを
式文として正規化する経路も追加した。Python/C標準Packには
新しいintrinsicの実現規則は登録していない。

既存のTargetのsupports宣言は意味保存の証明ではない。
基本操作の具体例、変換の実行時意味テストは第29回以降とする。

## 第35回：局所宣言の受理境界とPack工程への移行

**第35回：制御本体に閉じた宣言とModel拡張の一区切り**

明示型の初期値付き宣言が `if/else`、`while/else`、`for/else`、
`with` の本体で現れても、新規Constructや別のPythonブロックスコープを
導入せず、既存 `Block` の順序付き `Initialize` と、所属関数/モジュールの
`Symbol` で表す。新規変数は同じ本体の宣言以降か、そこに入れ子になった
本体からのみ参照できる。Python本来の束縛規則を変えるのではなく、
経路依存の未初期化を解析しないためにFrontendの受理を制限する。
宣言済み変数の書込みと通常の参照は維持する。

Port宣言と再束縛、try節直下の新規宣言、制御本体での新しい関数定義、
新規制御ローカル値・暗黙反復変数のlambda捕捉は対象外。
ModelにTargetの宣言の引き上げや一時値の配置を埋め込まない。
第31〜35回で予定した限定的なModel側の機能追加はここで終了。
次はPython Packを優先し、意味保存とContract照合を実使用から確認する。
C Packは一律の追随を義務付けず、必要な意味差の検証に用いる。
登録済みsupportsは生成コードの意味保存の証明ではない。

## 第34回：反復入口での束縛導入と型の静的決定

第34回では反復入口の束縛について、既存名への代入と新しい型付き名の導入を区別する `IterationEntry.introduces_binding` を追加した。Frontendは反復元の種類と厳密に単一の要素型からのみ導入型を確定し、Modelに存在しない初期化値を作らない。range、文字列、型付きList、同一要素型の非空Tupleに限定する。混合型・空Tuple・未知型は拒否する。

新規束縛はループ本体でのみ解決し、else節と終了後の参照は一般的な経路別初期化解析を避けるため受理しない。これはPythonのレキシカルスコープ規則の変更ではなくFrontendの受理制限である。既存Symbolは再利用し、終了後の参照も従来どおり許容する。`iteration_binding` と `for_iteration_binding` が導入形の `iteration.binding.introduced` 契約を要求し、標準C/Python Packはこの契約を宣言していないので、Realization追加前には拒否する。反復形式・for制御フローの既存の契約は維持する。Supports宣言は生成コードの意味保存の証明ではない。

## 第33回：省略を保持するスライスの意味境界

第33回では、`SliceValue` を型付きListとStringのスライスへ追加。
対象と開始・終了・ステップの境界式を一度ずつソース順に評価し、
境界の省略を明示的な0や負数へ安易に置き換えない。負ステップの
とき `s[::-1]` と `s[0::-1]` の違いが残る。Python添字の負値、
範囲外の切詰め、ゼロステップの実行時ValueErrorを意味契約として
登録したが、Model自身で添字演算を実行しない。

Listの結果は外側の新規容器を作る浅いコピーであり、要素の参照共有を
保つ。Stringの結果はUnicodeコードポイントを単位とする文字列。
種類に応じた契約は `sequence_slice` AdmissionRuleで照合する。
Tuple/Dictのスライス、スライス代入、一般の動的 `__getitem__`、
Realizationの新規レシピはまだ提供しない。宣言されたsupportsが
意味を保証するものではないため、Targetへの変換は個別に実証する。

## 第32回：List/Dict所属判定の型別意味と評価順

第32回は、`Membership(element, container, negate)` を型付き
List/Dict所属判定のために追加した。`StringContains` は既存の文字列
部分文字列判定として保持し、評価順を変更しない。文字列側にも
Unicode部分文字列と否定のAdmissionRuleを追加している。

`Membership` は左の対象式を先、右のコレクション式を後に各一度評価し、
Listでは順番に同一性または等値を調べ、Dictでは**キー**のハッシュ・等値
規則を用いる。否定形は判定結果を反転する。標準Target Packの対応は
追加しない。`collection_membership` AdmissionRuleを利用し、種類別の
意味契約・負の判定を明示的に照合できる。型推論、動的`__contains__`、
Tuple/Iterableの所属判定は今回対象外とした。

`StringContains` が文字列の専用Constructとして残るため、すべての
`in` が新しいConstructに統合されるわけではない。受理範囲の拡張と
Modelの意味保存を区別し、必要に応じてPack実行テストで検証する。

## 第29回：標準型変換と文字列基本メソッド

**第29回：具体的な標準Intrinsicの型付き意味契約**

第27〜28回で構築した操作系列・静的シグネチャ・署名固有obligationsを
標準の `str` / `int` / `float` 変換と `str.upper` / `str.lower` に適用した。
同じ `intrinsic.global.str` 系列でも整数・浮動小数点・真偽値・文字列・
無引数の契約を分けて、Targetに独立した支持表明を要求する。
浮動小数点の `str(1.0)` は `"1.0"` であり、一般の数値表示と
混同できない。変換例外やUnicodeの一対多文字対応も意味に含む。

この提供者表は操作の意味の採用であり、Runtimeの型変換実装ではない。
Frontendは型と個数のみ照合し、ソース式の実行や定数畳み込みをしない。
Modelの `IntrinsicCall` やAdmissionRuleは変更せず、従来の
`Length` / `Absolute` などを直ちに吸収しない。
Python/C標準Packにはレシピを追加しないため、受理できるModelの範囲と
Target上で実行・変換できる範囲は引き続き別物である。
個別Targetの意味保存はsupportsだけでは証明できない。

将来の文字列化の共通契約として利用できるが、print（出力）や
f-string（書式）への同一視、一般のobject.__str__等の動的解決は
今回の採用範囲ではない。可変list.appendの変更・別名共有も未採用。
