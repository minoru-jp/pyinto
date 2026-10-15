"""Model-sourced Construct/variant catalogue for Target authors.

This table is intentionally generated at canonical rendering time from the
installed source tree's public language interface, not copied by hand.
"""

from shikumi_devdoc.norms.common import canonical_source, summary
from shikumi_devdoc.norms.document import table_field, title

from pyinto.constructs import Construct
from pyinto.interfaces import language as lang

variants = table_field(
    "public Construct variants", columns=("Construct", "variant_domain()", "備考")
)


def language_variant_rows() -> tuple[tuple[str, str, str], ...]:
    """Deterministic catalogue of explicitly exported language Construct types."""
    rows: list[tuple[str, str, str]] = []
    for symbol_name in sorted(dir(lang)):
        value = getattr(lang, symbol_name)
        if not (isinstance(value, type) and issubclass(value, Construct)):
            continue
        if value is Construct:
            continue
        domain = value.variant_domain()
        rows.append(
            (
                symbol_name,
                ", ".join(f"`{item}`" for item in sorted(domain))
                if domain is not None
                else "開いた定義域 (`None`)",
                '`variant = "*"` で全variantに一致' if domain is None else "",
            )
        )
    return tuple(rows)


@summary(
    "pyinto.interfaces.languageで公開するConstructのvariant定義域をModel実装から生成した参照表。"
)
@canonical_source(
    "Construct / Variant Reference",
    filename="construct-reference.md",
    order=30,
    heading="title",
    merge_policy="local",
)
class CONSTRUCT_REFERENCE:
    """以下の表は`pyinto.interfaces.language`に公開されているConstructクラスから
    `variant_domain()`を参照して生成する。Realizerの実装者が存在しないvariantを推測しないための台帳。
    `pyinto.constructs`のその他の外部拡張型・任意の外部提供者まで網羅するものではない。

    - `frozenset`：登録時にvariant名を厳密検証する。
    - `None`：候補を構築時に列挙できない開いた定義域。`"*"`で包括的に扱える。
    - `variant = "*"`：今後追加されるvariantを含む全てに一致。
    - `variant`省略：`"default"`だけを指定（`default`が存在しない型は拒否）。
    - `Call`：直接builtin Callは一部、Constructクラスのvariantとは別の名前登録経路を使用。

    **注意**：表に掲載したことはFrontendがどのPython構文でも生成できること、Targetが
    それを実現できること、意味保存を保証することを意味しない。
    個々のConstructの`parts()`と契約は[Specification](../specification/INDEX.md)を参照。
    """

    class VARIANTS:
        """同一クラスの別名公開が発生した場合も、**公開名**を表のキーとして保持する。
        自動生成表なので、Constructのvariant追加後は`python scripts/docs.py render`で更新する。
        """

        title @= "公開Constructのvariant一覧"
        for _row in language_variant_rows():
            variants @= _row
