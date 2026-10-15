<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/vocabulary/canonical.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# pyinto 用語集

現行実装のAPI名と区別した、Model化・Realizer・合成の共有用語。

## Model

1つのSourceからFrontendが作る、Constructの木（`Program`）。変換対象となる
構造・機能・操作とその意味契約をTarget非依存に表し、特定Targetの実現方法は
含めない。部品の種類を指すときはConstruct、抽象層全体を指すときは
「Modelの層」と呼び分ける。`pyinto.model`はModelを作る部品の置き場であり、
`Model.language.Branch`等の統一名前空間APIは未実装。

## Construct

Modelの具体的な要素を表す型・インスタンス。構造や名前付き子要素を持ち、
Target固有のコード生成を担わない。汎用基底`Construct`は維持する。
言語構造を表すConstructは「Language Construct」と呼び分ける。

## Interface

Python上で実行可能なSource API（言語構文も含む）と、Target非依存の
Construct・意味契約というModel側の公開面を結び付ける意味上の単位。
Python上の具体的処理を伴っていてよく、Javaのinterface型に限定しない。
BuiltinsのPython実行はPython自身が提供し、追加ライブラリは既存の
Pythonライブラリまたは提供者の実装が担当する。両面の対応付け機構は
Interface Mappingであり、Target上の実現は別のRealizationが担当する。
現行`pyinto.interfaces.language` / `builtins` は既存Constructの公開窓口で、
汎用Interface登録器やPython側実装のラッパーを新設するものではない。

## Realization

Constructの構造と意味契約に対し、Target上の具体的な実現規則を提供するもの。
旧Bindingに相当し、Templateや動的な実現計画・補助要件、
Model構造順のVisitor等を含み得る。
生成済みソース文字列そのものや、意味保存を自動証明する機構ではない。

## Template

Realizationが提供する配置関係を、固定テキストとSlotなどで保持する
未文字列化の合成構造。完成済みコード文字列とは限らない。

## Slot

Template内で別のModel要素に対するRealizationを接続する位置。
子の実現が再帰的に続き得る接点であり、単なる文字列置換の穴ではない。

## Frontend

Pythonの構文、明示的な型、参照と登録済み外部APIの情報を読み取り、
Constructへ正規化する機構。`PythonFrontend`はHost内の実装クラス。
Target固有の表記や実現方法は決定しない。

## Composer

Realizationを解決し、TemplateのSlotへ子の実現結果を再帰的・機械的に
接続する機構。Targetの意味論を推測して補完しない。

## Renderer

合成されたTemplate／Slotの構造を、最終的に出力ソース文字列へ変換する機構。
未指定の実現や意味を推測して追加しない。

## Target

成果物の実現先となる言語・環境・形式。CやRust等のコード生成は主要な用途。
ModelはTargetに依存せず、具体的な実装単位とは区別する。

## Realizer

あるTarget向けのRealizationを束ねた実装一式。例：C Realizer
（`tests/support/c_realizer/`）。入口の宣言がTarget Pack、中の個々の規則が
Realizationであり、生成状態と成果物はRealizerが管理する。言語構造向けの
Language Implementationと、抽象Interface向けのInterface Implementationを含む。
新しい共通基底クラスを意味しない。旧文書の「Target Implementation」
「Target Cartridge」に当たる。

## Contract

Modelの操作、型、制約、評価順序・退出などの意味上の要求。
Construct提供者のAdmissionが必要な契約を宣言し、Target側の
`supports`と照合する。照合の成功は生成コードの意味保存の証明ではない。
開発テストに用いるShikumi-Contraceの契約定義とは区別する。

## 決定論的な導出

明示された構造、参照、契約、選択されたRealizationに従って成果物を構成すること。
実行結果を推測することや、Target上で必ず正しく動作すると証明することではない。

## pyinto

本プロジェクトとHostのPython配布名。変換元PythonのModel化と変換入口を提供する。
旧公開名はhenkan（さらに以前はSkeleton）。旧候補名taiouは採用しない。

## Host

`pyinto`本体のリポジトリ分類名。利用者向けSurface、共通Foundation、
言語構造Interface、Python Source Adapterを同一の開発・配布単位で扱う。
特定のRealizerはHost配布物に含めない。

## Surface

`convert()`・`realize()`等の変換利用者向け入口を指す論理的役割。
Host全体の別名ではない。CLIは現時点で未実装。

## Foundation

Construct・Admission・Realizationの登録、合成、描画等の共通機構という
論理的役割。独立の配布パッケージを新設したことを意味しない。

## Language Construct

`Branch`、`While`、`Arithmetic`など、Pythonから正規化する言語構造を
表現したConstructの分類。現行ではHostに含まれる。
汎用基底クラス`Construct`の名称は変更しない。

## Python Source Adapter

変換元Pythonの構文や型・名前をModelに正規化するHost内の論理的役割。
実装は`PythonFrontend`等を用いる。交換可能な複数Frontendを提供するという意味ではない。

## Interface Mapping

Python側で登録済みの外部関数・クラス・メソッド等の表現を、対応するConstructへ
結び付ける定義・機構。現行APIは`InterfaceMappingRegistry`等。
抽象Interface自体の定義ではなく、Kindの`@Interface`とも別である。関数の対応付けを
関数マッピング、クラスの対応付けをクラスマッピングと呼ぶ。クラスマッピングで
生成したオブジェクト（マップ済みオブジェクト）は、Model上で`MappedType`・
`ValueKind.MAPPED_OBJECT`・型表記の鍵`mapped:`で表す。

## Language Implementation

Language ConstructをあるTargetで実現するRealizer。
Cの参照実装は現在`tests/support/c_realizer/`にあり、
公開Hostの配布パッケージには含めない。

## Interface Implementation

抽象Interfaceが定義したConstructを、あるTargetの言語・ライブラリ等で
実現するRealizer。個別の利用ライブラリとの1対1対応は必須でない。

## Bundle

複数のInterfaceやRealizer等を組み合わせた公開単位の暫定名。
自動発見・合成・配布の専用機構は現時点で未実装。

## Kind

`pyinto.kinds` が提供する、Targetへ型・メモリ・宣言の情報を渡すための語彙。
公開面 `datatypes` / `memory` / `declarations` と、全Targetが解釈する
`general` の段・言語に近い選択肢である `detailed` の段に分かれる。
Hostは意味を定義せず、ラベルとしてModelに記録しTargetへ渡すだけで、
具体的な表現の選択と実行結果はTargetとそのコードに属する。

## Source

pyinto向けに書くPythonのテキスト。Hostが読み、Modelに正規化する。
`__pyinto_runtime__` を使う場合を除き、Pythonとして実行されることは想定しない。

## Target Pack

Realizerの入口となる宣言クラス。`target`・`entries`・`dispatch`・`session`
などを通常のクラス属性で宣言し、`RealizationRegistry.from_pack()` に渡す。
Realizerそのものではなく、その宣言の形を指す。

## Artifact

Realizerが出す成果物。`convert()` / `realize()` の戻り値であり、
文字列に限らず任意のオブジェクトでよい。Hostは中身を解釈しない。
