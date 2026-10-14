<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/target_implementation/verification_guide.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# Target Verification Guide

**完了の定義**：実装したPackの公開API登録、想定したModelの受理、
未対応Modelの拒否、成果物の形状・内容、意味保証の根拠、要求ごとの独立Sessionを
テストで確かめる。テストが成功していないことを「対応済み」と書かない。

この文書自体の掲載例は[Implementation Guide](implementation-guide.md)と同じ
canonical source内の検証対象スニペットを使用し、pytestで実行する。
`tests/support/c_realizer/`は回帰用の参照実装であり、公開Target Packではない。

## 実装と文書の検証手順

作業順序：

1. `RealizationRegistry.from_pack(Pack)`をテストし、宣言検証の失敗例も作る。
2. `convert`/`realize`に最小入力と複数ノードを渡し、成果物を具体値で比較する。
3. `variant`の個別/`*`優先、宣言漏れ、未知variant、未処理ポリシーをテストする。
4. Preservationなら各required_contractsを確認し、不足時の拒否と
   実行時の意味保存を**別々に**テストする。
5. Projectionなら未登録Realizerの通過と、未登録Model自体の拒否を
   **区別して**検証する。
6. 同じRegistryで異なる2入力を連続処理し、Session状態が混ざらないことを検証する。
7. Hostが成果物を勝手に文字列化しないことと、入力Constructを変更しないことを確認する。

**テスト例の実行**：リポジトリルートで
`python -m pytest tests/test_target_documentation.py -q`。
文書生成状態は `python scripts/docs.py check` で確認する。
Hostの検証基準はRuff、basedpyright、既存pytest + Contrace。

## 受け入れテスト・マトリクス

すべての項目が全Targetに必須とは限らない。
対象外の機能を対応済みと推測せず、テストの対象外であることを明記する。

completion checks:

| 確認対象 | 正常系 | 拒否系 / 注意 |
| --- | --- | --- |
| Pack宣言 | Pack名と方式を読み出せる | 不正なdispatch/semantics/unhandled/重複登録は拒否 |
| variant | 個別指定を*より優先 | 無効な既知variant、曖昧な省略を拒否 |
| Structural | parts()順の先行訪問とctx.path | visitの非None戻り値を拒否 |
| Composition | TemplateのSlot再帰合成とLayout提出 | 未存在Slot/無効Template/未処理実現を拒否 |
| Projection + traverse | 一致しないRealizationを通過して子へ | Admission未登録のModelは通過不可 |
| Preservation | supportsが必要契約を満たす | 不足時に描画/Visitorより前に拒否 |
| Session | 入力ごとに別の状態を作る | 古い成果物が次の要求へ漏れない |
| Artifact | Target固有の型と内容を保つ | Host側でstr化・暗黙のコード化を行わない |

## 完了判定に含めない誤った推論

- `pack_semantics="projection"`は抽出の正確性まで自動証明しない。
- `supports`は実行意味の保証を自動証明しない。保存型Targetでは生成物の動作を別途検証する。
- CompositionではTemplateが参照しない子Constructは自動で出力されない。
- Structuralは先行順の単一Visitor呼び出しであり、子終了フックは現段階ではない。
- 参照用C/Python Targetの機能範囲を一般Targetの実現可能性と同一視しない。
- 文書生成チェックはランタイムの意味正しさを保証しない。
