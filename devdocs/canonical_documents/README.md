<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/readme/canonical.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# pyinto

Pythonコードをソースとして任意の形式(他言語コード、バイナリなどなんでも)及び内容へ変換するためのフレームワーク。

- ただし、任意のpythonコードをソースとして用いることはできない。

## まだAlphaなので破壊的変更があります。

現在の実装状況については、[STATUS](STATUS.md) を参照。

## インストール

Python 3.11以降が必要です。

```bash
pip install pyinto
```

## 概念モデル

pyintoは、Pythonコードから抽出した構造と意味を、特定の出力形式に依存しないModelとして扱う。

Target Implementationは、このModelを基に成果物を生成する。

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

- Host側でModel化されていないpythonの構文はHost側に入力された時点で拒絶される。
- また、Host側が受理したものでもTarget Implementation側が対応していない場合はやはり拒絶される。
- つまり、このフレームワークでは任意のpythonコードを変換ソースとして使用することはできず、Model化されていて、かつTarget Implementation が対応している`制限されたpythonコード`のみを変換ソースとして使用することができる。

## 主な使い道とそれ以外の利用方法について

### 他言語のソースファイルへの変換
もともとこれを作成した動機であり、Target Implementationを作成することによって任意の言語への変換が可能になると想定している。しかし、現時点では完成された特定言語への変換を実現するTarget Implementationは存在していない。

#### ModelとRealizationの概念の組み合わせはライブラリにも適用する
特定の言語への基本的な変換を実装しようとする際に、そこで使用するライブラリまで含めてその時点で実装する必要はない。
python標準ライブラリであってもHostはModelを提供していない。
ライブラリのModel化は必要に応じて行う。そして対応するRealizationを作る必要がある。
このとき、Model化されたライブラリインターフェースは特定の言語に依存しなくてもよいため、言語に依存するのではなくて、「一般的な」処理手順に依拠する形で資産化できる可能性がある。しかし、これもまだ検証段階で、はっきり示すことはできない。

### python構文と、モジュールの実行結果を利用した成果物の生成
制限されたpythonコードを前向きに捉えて、「ミニ言語」として利用する。また、拡張ではなくて、制限なので変換元コードは実行可能なものである。これらの性質（ASTを利用した静的解析要素と実行することによって得られる動的な状態）を組み合わせて、最終的な成果物を作成する。
`__pyinto_runtime__` という名称で定義した関数はモジュール内で特別な意味を持ち、ASTの解析対象から外される。この関数の戻り値はTarget Implementationが最終的に成果物を生成する際にHostから与えられ、この情報を成果物に反映させることができる。

### LLMとの協調開発について
このようにHostを小さく保ち、それ以外を外側で全て定義するような方法はLLMによる実装を前提としている。

Target Implementationの実装の仕方については [Target Implementation Guide](target_implementation/INDEX.md) を参照。


## ドキュメント

詳細な情報は、以下の文書を参照。

| 文書 | 内容 |
|---|---|
| [STATUS](STATUS.md) | 現在の開発状況、実装済み機能、制限事項 |
| [Target Implementation Guide](target_implementation/INDEX.md) | Target Implementationの開発ガイドライン |
| [Specification](specification/INDEX.md) | pyintoの仕様と動作契約 |
| [Glossary](GLOSSARY.md) | プロジェクトで使用する用語の定義 |
| [Changelog](CHANGELOG.md) | 開発履歴と変更内容 |

Target Implementation Guideは、特にLLMによる実装作業で利用することを想定して構成されています。

現在、公式文書は日本語で整備しています。

## ライセンス

ライセンスについては、リポジトリの [LICENSE](../../LICENSE) ファイルを参照してください。
