"""README の日本語 canonical source。

プロジェクトの位置付けと導線に限定し、詳細な仕様は専門文書へ委ねる。
"""

from shikumi_devdoc.norms.common import canonical_source
from shikumi_devdoc.norms.document import title


@canonical_source(
    "pyinto",
    filename="README.md",
    merge_policy="external",
    heading="title",
)
class README:
    """**pyintoは、型付きPythonコードをTarget非依存のModelへ正規化し、Target Implementationによって多様な成果物へ具体化するためのHostライブラリです。**"""

    class DevelopmentStatus:
        """pyintoは現在、**Alpha段階の実験的なライブラリ**です。

        API、Model、仕様、その他の設計は、今後の開発によって変更される可能性があります。

        特に、**予告や移行期間を設けず、後方互換性のない破壊的変更を行う場合があります。**

        現段階では、APIの安定性や既存バージョンとの互換性を保証していません。
        本番環境での利用や継続的な依存関係としての採用には十分注意してください。

        現在の実装状況については、[STATUS](STATUS.md) を参照してください。
        """

        title @= "⚠️ 開発状況について"

    class Installation:
        """Python 3.11以降が必要です。

        ```bash
        pip install pyinto
        ```
        """

        title @= "インストール"

    class ConceptualModel:
        """pyintoは、Pythonコードから抽出した構造と意味を、特定の出力形式に依存しないModelとして扱います。

        Target Implementationは、このModelを基に成果物を生成します。

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
                      │     Target      │
                      │ Implementation  │
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

        この構造では、**Modelの構築とRealizationの実行制御をHostが担当し、成果物の構築と提出をTarget Implementationが担当します。**
        """

        title @= "概念モデル"

    class HostResponsibilities:
        """pyinto Hostは、主に以下を提供します。

        - **Frontend**：型付きPythonコードを静的に解析し、Modelへ正規化する。
        - **Construct Model**：プログラムの構造と意味をTarget非依存の形式で表現する。
        - **Admission**：ModelとRealizationに関する契約を検証する。
        - **Realization Dispatch**：Modelの構造や宣言された実行方式に従ってRealizerを呼び出す。

        Hostは成果物の種類や内部形式を規定しません。
        """

        title @= "Hostの役割"

    class TargetResponsibilities:
        """Target Implementationは、Hostから提供されるModelの情報を利用し、目的に応じた成果物を生成します。

        各Target Implementationは、Realizationの定義、生成状態の管理、成果物の構築と提出を担当します。

        主な用途は、Pythonコードから他のプログラミング言語への変換です。

        ただし、**生成できる成果物の形式にHost側の制限はありません。**
        Target Implementationが実現できるものであれば、ソースコードだけでなく、
        構造化データ、図、文書、解析結果など、幅広い成果物を扱えます。
        **テキストに限らず、画像や実行形式などのバイナリファイルも生成対象にできます。**
        成果物が必ずファイルである必要もありません。

        また、Target Implementationは目的に応じて、Modelの実行意味を保存する方式と、
        必要な情報を射影する方式を選択できます。
        """

        title @= "Target Implementationの役割"

    class Dispatch:
        """pyintoは、Realizerを呼び出すために2種類の方式を提供します。

        **Composition**

        Template/Slotに基づいてRealizationを再帰的に呼び出し、構造を合成する方式です。

        主に、プログラミング言語のソースコードなど、構造的なテキスト生成に適しています。

        **Structural**

        Modelの構造を走査し、対応するRealizerを呼び出す方式です。

        主に、Modelからの情報抽出、構造解析、図や構造化データの生成などに適しています。

        いずれの方式でも、最終的な成果物の管理はTarget Implementationが担当します。
        """

        title @= "Realizationの実行方式"

    class TargetImplementations:
        """**pyintoはHostライブラリであり、具体的なTarget Implementationを配布しません。**

        したがって、pyintoをインストールしただけでは、Cやその他のプログラミング言語への変換機能は利用できません。

        成果物を生成するには、目的に対応したTarget Implementationを別途用意する必要があります。

        Target Implementationは、pyintoが公開するModel、Realization、Admissionなどの
        インターフェースを利用して開発できます。

        リポジトリの `tests/support/` には、Hostの検証に使用するPythonおよびCのRealizerが含まれています。
        これらは開発・テスト用の参照実装であり、pyintoの配布パッケージには含まれません。

        Target Implementationの作成方法については、以下のガイドラインを参照してください。

        **[Target Implementation Guide](target_implementation/INDEX.md)**

        このガイドラインでは、Targetの設計、Realizationの宣言、Constructとvariant、
        意味契約、成果物の生成、検証方法を扱っています。
        """

        title @= "Target Implementationについて"

    class Documentation:
        """詳細な情報は、以下の文書を参照してください。

        | 文書 | 内容 |
        |---|---|
        | [STATUS](STATUS.md) | 現在の開発状況、実装済み機能、制限事項 |
        | [Target Implementation Guide](target_implementation/INDEX.md) | Target Implementationの開発ガイドライン |
        | [Specification](specification/INDEX.md) | pyintoの仕様と動作契約 |
        | [Glossary](GLOSSARY.md) | プロジェクトで使用する用語の定義 |
        | [Changelog](CHANGELOG.md) | 開発履歴と変更内容 |

        Target Implementation Guideは、特にLLMによる実装作業で利用することを想定して構成されています。

        現在、公式文書は日本語で整備しています。
        """

        title @= "ドキュメント"

    class License:
        """ライセンスについては、リポジトリの [LICENSE](../../LICENSE) ファイルを参照してください。"""

        title @= "ライセンス"
