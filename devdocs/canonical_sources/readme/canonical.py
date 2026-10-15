"""README の日本語 canonical source。"""

from shikumi_devdoc.norms.common import canonical_source


@canonical_source(
    "pyinto",
    filename="README.md",
    merge_policy="external",
    heading="title",
)
class README:
    """
    Pythonコードをソースとして任意の形式(他言語コード、バイナリなどなんでも)及び内容へ変換するためのフレームワーク。

    - ただし、任意のpythonコードをソースとして用いることはできない。
    - 稼働している既存のPythonプログラムを他の言語へ移植するためのものではない。目的は変換であり、ソースはTargetへ情報を渡すための記述として扱う。
    - `__pyinto_runtime__` を使う場合を除き、ソースがPythonとして実行されることは想定しない。

    ## まだAlphaなので破壊的変更があります。

    現在の実装状況については、[STATUS](STATUS.md) を参照。

    ## インストール

    Python 3.11以降が必要です。

    ```bash
    pip install pyinto
    ```

    ## 概念モデル

    pyintoでの変換は、次の流れで進む。

    ```text
    Source ──(Host)──▶ Model ──(Realizer)──▶ Artifact
    ```

    - **Source**：pyinto向けに書くPythonのテキスト。
    - **Host**：pyinto本体。Sourceを読んでModelを作り、Realizerを呼ぶ。
    - **Model**：1つのSourceから作られる、Construct（部品の種類）の木。特定の出力形式に依存しない。
    - **Target**：出力先の言語や形式（C、Rust、JSONなど）。
    - **Realizer**：あるTarget向けの実装一式。中の個々の規則をRealizationと呼び、入口の宣言をTarget Packと呼ぶ。
    - **Artifact**：Realizerが出す成果物。

    各段の中身は次のとおり。

    ```text
                  Typed Python Source
                           │
                           ▼
                  ┌─────────────────┐
                  │   pyinto Host   │
                  │                 │
                  │    Frontend     │
                  │       ↓         │
                  │ Construct Model │
                  │       ↓         │
                  │    Admission    │
                  │       ↓         │
                  │    Dispatch     │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │    Realizer     │
                  │                 │
                  │  Realizations   │
                  │       ↓         │
                  │ Artifact State  │
                  │       ↓         │
                  │  Finalization   │
                  └────────┬────────┘
                           │
                           ▼
                        Artifact
    ```

    - Host側でModel化されていないpythonの構文はHost側に入力された時点で拒絶される。
    - また、Host側が受理したものでもRealizerが対応していない場合はやはり拒絶される。
    - つまり、このフレームワークでは任意のpythonコードを変換ソースとして使用することはできず、Model化されていて、かつRealizerが対応している`制限されたpythonコード`のみを変換ソースとして使用することができる。

    ## 主な使い道とそれ以外の利用方法について

    ### 他言語のソースファイルへの変換
    もともとこれを作成した動機であり、Realizerを作成することによって任意の言語への変換が可能になると想定している。しかし、現時点では完成された特定言語への変換を実現するRealizerは存在していない。

    #### ModelとRealizationの概念の組み合わせはライブラリにも適用する
    特定の言語への基本的な変換を実装しようとする際に、そこで使用するライブラリまで含めてその時点で実装する必要はない。
    python標準ライブラリであってもHostはModelを提供していない。
    ライブラリのModel化は必要に応じて行う。そして対応するRealizationを作る必要がある。
    このとき、Model化されたライブラリインターフェースは特定の言語に依存しなくてもよいため、言語に依存するのではなくて、「一般的な」処理手順に依拠する形で資産化できる可能性がある。しかし、これもまだ検証段階で、はっきり示すことはできない。

    ### python構文と、モジュールの実行結果を利用した成果物の生成
    制限されたpythonコードを前向きに捉えて、「ミニ言語」として利用する。Targetが `__pyinto_runtime__` を要求する場合に限り、Hostはソースを通常のPythonとして実行する。ASTを利用した静的解析要素と、その実行によって得られる動的な状態を組み合わせて、最終的な成果物を作成する。
    `__pyinto_runtime__` という名称で定義した関数はモジュール内で特別な意味を持ち、ASTの解析対象から外される。この関数の戻り値はRealizerが最終的に成果物を生成する際にHostから与えられ、この情報を成果物に反映させることができる。

    ### Kindの語彙（`pyinto.kinds`）
    Targetに型・メモリ・宣言の情報を渡すため、`pyinto.kinds` が語彙を提供する。公開面は `datatypes`（値が何であるか）、`memory`（どこに置き、誰が持ち、いつ手放すか）、`declarations`（クラスなどの宣言の性格）に分かれ、それぞれ2段に分かれる。

    - `general`：どの言語のTargetも解釈を定める汎用語彙。Pythonの組み込み型（`int`、`float` 等）と、`Wide[int]`、`Unsigned[int]`、`Size`、`Owned[T]`、`Memory.release` 等。これだけで書いたソースは、汎用語彙に対応したどのTargetでも変換できる。
    - `detailed`：各言語の表現に近い選択肢。`Int[32]`、`Pointer[T]`、`Null`、`@Interface` 等。対応しないTargetは拒否してよい。

    ```python
    from pyinto.kinds.datatypes.general import Unsigned, Wide
    from pyinto.kinds.memory.general import Memory, Owned

    total: Unsigned[Wide[int]] = 0
    cell: Owned[int] = Memory.new(int, 7)
    Memory.release(cell)
    ```

    Hostはこれらの意味を定義せず、ラベルとしてModelに記録してTargetへ渡すだけである。具体的にどう書くかはTargetが選ぶ。

    ### LLMとの協調開発について
    このようにHostを小さく保ち、それ以外を外側で全て定義するような方法はLLMによる実装を前提としている。

    Realizerの実装の仕方については [Realizer Guide](realizer/INDEX.md) を参照。


    ## ドキュメント

    詳細な情報は、以下の文書を参照。

    | 文書 | 内容 |
    |---|---|
    | [STATUS](STATUS.md) | 現在の開発状況、実装済み機能、制限事項 |
    | [Realizer Guide](realizer/INDEX.md) | Realizerの開発ガイドライン |
    | [Specification](specification/INDEX.md) | pyintoの仕様と動作契約 |
    | [Glossary](GLOSSARY.md) | プロジェクトで使用する用語の定義 |
    | [Changelog](CHANGELOG.md) | 開発履歴と変更内容 |

    Realizer Guideは、特にLLMによる実装作業で利用することを想定して構成されています。

    現在、公式文書は日本語で整備しています。

    ## ライセンス

    ライセンスについては、リポジトリの [LICENSE](../../LICENSE) ファイルを参照してください。
    """
