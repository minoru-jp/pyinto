<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/realizer/implementation_guide.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# Realizer Guide

対象と前提

pyinto 0.2.0 Alpha の **Host** を利用する独立した Realizer の実装者向け。
目的はPython ASTを直接処理することではなく、Frontendで正規化したConstruct Modelを
Hostの呼び出し規則で受け取り、Target独自の成果物を提出すること。

**判断の優先順位**：公開APIのシグネチャ、[Declaration Reference](declaration-reference.md)、
[Construct / Variant Reference](construct-reference.md)、
[Admission Reference](admission-reference.md)、既存[Specification](../specification/INDEX.md)。
`tests/support/` のC/Python Realizerは参照実装であり、Hostの配布パッケージには含まれない。
不明なAPI、variant、契約名、未対応機能を推測で埋めない。

## 最初に決定する2軸と未処理ポリシー

**成果物の型**（文字列/bytes/辞書/複数ファイルを表す独自オブジェクト）はTargetが決める。
Dispatch（呼び出し方法）とSemantics（意味保証）は独立した判断である。

decision matrix:

| 問い | 選択 | 根拠 |
| --- | --- | --- |
| TemplateのSlotが子の呼び出しを決める | composition | 既存の遅延Layout合成を利用する |
| parts()のConstructを順に観測する | structural | 深さ優先の先行順。子終了通知はない |
| 実行意味を保つ成果物を作る | preservation | 既定値。各Realizationのsupportsを照合 |
| 構造や情報のみを抽出する | projection | 実行意味のsupports照合を要求しない |
| 一部のConstructだけ観測する | structural + projection + traverse | 一致しないvariantのVisitorを省略して子を訪問 |

## 実装の7手順

1. 対象のPython入力と出力形式、**保存/射影する意味**を記述する。
2. `dispatch`、`semantics`、`unhandled` を選択する。
   省略時は順に `composition`、`preservation`、`error`。
3. Realizationを `@realizes(lang.<Construct>)` で登録し、
   `structural`では`visit`、`composition`では`template`または`render`を定義する。
4. `session`を定義する。Sessionは**要求ごとに新規生成**され、`finish()`を持つ。
   `composition`ではさらに`accept_composition(layout, context)`を持つ必要がある。
   文字列成果物には`TextArtifactSession`を利用できる。
5. `entries` に登録するクラスを全て明示し、
   `RealizationRegistry.from_pack(Pack)`で宣言を検証する。
6. `convert(source, realizations=registry)`、またはModelがある場合は
   `realize(model, realizations=registry)`を実行して成果物を取得する。
7. 必ず[Verification Guide](verification-guide.md)に従って受理・拒否・独立セッションを確認する。

Hostは**Realization呼び出しとModelのAdmission検査**を所有する。
成果物の構築・順序・提出はTarget Sessionが所有する。
`ctx.session`はTargetに所有権があるが、`ctx.path`のConstructは書き換えない。

## 実行可能例：Structural + Projection

最小の射影Target。関数名と戻り値型だけを収集し、未登録の構造は通過する。
**この例は実際のAPIで実行する検証対象**。貼り付けてそのまま実行できる。

```python
from pyinto import convert
from pyinto.constructs import Construct
from pyinto.interfaces import language as lang
from pyinto.realizations.registry import EmitContext, RealizationRegistry
from pyinto.realizations.regulation import realizes


class OutlineSession:
    def __init__(self):
        self.names = []

    def finish(self):
        return self.names


def collect(node: Construct, ctx: EmitContext) -> None:
    assert isinstance(node, lang.FunctionDefinition)
    assert isinstance(ctx.session, OutlineSession)
    ctx.session.names.append(
        (node.signature.name, node.signature.return_type.annotation())
    )


@realizes(lang.FunctionDefinition)
class FunctionOutline:
    visit = collect


class OutlinePack:
    target = "outline"
    dispatch = "structural"
    semantics = "projection"
    unhandled = "traverse"
    session = OutlineSession
    entries = (FunctionOutline,)


registry = RealizationRegistry.from_pack(OutlinePack)
source = "def add(a: int, b: int) -> int:\n    return a + b\n"
assert convert(source, realizations=registry) == [("add", "int")]
```

この例の`visit`は値を返さず、Sessionの状態だけを更新する。
`traverse`は不明な**Realization**の通過であって、不明な**Construct型**のAdmission免除ではない。

## 実行可能例：Composition + TextArtifactSession

最小のTemplate/Slot合成例。出力はTargetが選んだ`TextArtifactSession.finish()`の結果。
Hostから受け取るのは中間Layoutであり、Hostは最終文字列を自動的に成果物化しない。
**例は整数値式1種類のみ**を表し、汎用的な意味保存型コード変換器ではない。

```python
from pyinto import realize
from pyinto.constructs import Block, ExpressionStatement, Literal, Program
from pyinto.interfaces import language as lang
from pyinto.realizations import RealizationRegistry, TextArtifactSession
from pyinto.realizations.regulation import realizes


@realizes(lang.Program)
class ProgramRule:
    template = "${body}"


@realizes(lang.Block)
class BlockRule:
    template = "${children}"


@realizes(lang.ExpressionStatement)
class ExpressionRule:
    template = "${expression};"


def integer(node, ctx):
    assert isinstance(node, lang.Literal)
    return str(node.value)


@realizes(lang.Literal)
class IntegerRule:
    variant = "integer"
    render = integer


class TextPack:
    target = "demotext"
    dispatch = "composition"
    session = TextArtifactSession
    entries = (ProgramRule, BlockRule, ExpressionRule, IntegerRule)


registry = RealizationRegistry.from_pack(TextPack)
model = Program(Block((ExpressionStatement(Literal(2)),)))
assert realize(model, realizations=registry) == "2;\n"
```

実際の意味保存Targetでは未対応variant/契約を拒否し、動作を実行テストで検証する。
`${...}`はPython f-stringではなくTemplate Slotである。
Templateが参照しない子はCompositionで自動実現されない。

## LLMが補完・推測してはいけない点

- `@realizes(lang.Literal)` の省略は**全variantではなく`default`**。
  Literalの定義域は`integer/string`なので、この省略宣言は拒否される。
- `Return`の省略は`default`だけを表す。値あり`with_value`を処理するなら
  明示するか `variant = "*"` を選ぶ。
- Structural + Projectionの複数variant/開いた定義域では省略を禁止する。
  `"*"`は将来追加されるvariantも捕捉し、個別宣言が優先する。
- `projection`は**任意の嘘が許されるモードではない**。
  出力を正しく記述し、必要な射影内容はTarget側で検証する。
- `supports`は意味保存の**自己宣言**であり、実行意味が保証された証明ではない。
- `ctx.path`から祖先/深さは読めるが、Structuralの後処理イベントはない。
- Realization、Registry、Packの名前による自動登録やTarget自動探索はない。
