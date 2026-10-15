"""Admission obligations and semantic promises for Target implementations."""

from shikumi_devdoc.fields.specification import MUST, level, related
from shikumi_devdoc.norms.common import canonical_source, summary
from shikumi_devdoc.norms.document import table_field, title

from devdocs.canonical_sources.specification.composition import (
    SPECIFICATION_PART as COMPOSITION_SPEC,
)
from pyinto.constructs.admission import LANGUAGE_ADMISSION

obligations = table_field(
    "admission rule catalog",
    columns=("Rule", "対象Construct", "宣言可能な契約キー/ファミリー"),
)
conditions = table_field(
    "semantics and admission", columns=("モード", "必須検査", "実装者の責任")
)


def baseline_rule_rows() -> tuple[tuple[str, str, str], ...]:
    """Use the actual baseline declaration, not a hand-maintained key list."""
    rules = {
        rule.name: rule
        for declaration in LANGUAGE_ADMISSION.declarations
        for rule in declaration.rules
    }
    return tuple(
        (
            name,
            ", ".join(cls.__name__ for cls in rule.constructs),
            ", ".join(f"`{key}`" for key in sorted(rule.contracts)),
        )
        for name, rule in sorted(rules.items())
    )


@summary("意味保存と射影、Admission提供者の登録検査、supports宣言、拒否の境界。")
@canonical_source(
    "Admission Contract Reference",
    filename="admission-reference.md",
    order=40,
    heading="identity",
    merge_policy="local",
)
class ADMISSION_REFERENCE:
    """Targetの`semantics`は成果物の**主張する意味保証**を選択する。
    変換先のファイル拡張子や、`dispatch`から自動的には推測しない。
    既存の規範契約は[Composition Specification](../specification/composition.md)にあり、
    このReferenceはTarget作者が誤宣言しないための適用ガイドである。
    """

    class ADM_001:
        """HostはRealization選択やSession生成の前に`admission.check_tree(root)`を行う。
        Modelの具体的なConstruct型が提供者のAdmissionへ登録されていなければ、
        `unhandled="traverse"`でも拒否する。
        `realize(..., admission=...)`で拡張Admissionを渡すときは基準の
        `LANGUAGE_ADMISSION`を削除・置換できない（`require_baseline`）。
        `convert(..., interface_mappings=...)`ではMapping側のAdmissionが使われる場合がある。
        """

        title @= "Model受理とTarget受理は異なる"
        level @= MUST
        related @= (COMPOSITION_SPEC.CMP_018,)

    class ADM_002:
        """Preservation（省略時）では、対象Constructの
        `admission.required_contracts(node)`から必要契約を取り出し、
        選択したRealizationの`supports`集合との**差集合**が空でなければ
        `ConstructError`で拒否する。構造上到達しても必要な意味を保存できないなら
        宣言を捏造せずTarget側で拒否する。
        `supports`は意図した保証の自己宣言であり、コード実行結果の検証が別途必要。
        """

        title @= "意味保存の要求契約"
        level @= MUST
        related @= (COMPOSITION_SPEC.CMP_013, COMPOSITION_SPEC.CMP_017)

    class ADM_003:
        """Projectionでは実行意味を成果物へ再現する必要がないため、
        個別Realizationへの`required_contracts - supports`の照合を**要求しない**。
        この緩和は未登録Modelの使用や、成果物に含める情報の誤報を許容するものではない。
        何を抽出したかを明示し、その情報の正しさをテストする。
        **射影の正しさについて汎用の契約自動検証は現行未実装**。
        """

        title @= "意味射影の適用範囲"
        level @= MUST

    class ADM_004:
        """`unhandled="error"`は一致するRealizationがなければ拒否する。
        `"traverse"`を使えるのはStructural + Projectionのみ。
        その場合、一致しないConstructのVisitorを実行せず、`parts()`配下のConstructへ進む。
        同じ型の別variantでも、正当な個別指定をしている場合は通過する。
        非対応の型・variantを全て実現したと主張してはいけない。
        """

        title @= "未処理とAdmissionの二層の境界"
        level @= MUST

    class ADM_005:
        """具体的な契約名をコードの類推だけで捏造しない。
        対応するModelのAdmission Rule、`required_contracts(node)`、
        関連Specification、動作テストを確認する。
        Variant選択の網羅性は`Construct.variant_domain()`の登録検証と
        `variant = "*"`の明示宣言で扱うが、意味契約との一致を代替しない。
        """

        title @= "契約名の確認とvariantの独立性"
        level @= MUST

    class CATALOG:
        """以下の一覧は`LANGUAGE_ADMISSION.declarations`のRuleから生成する。
        `contracts`にある`.*`は**提供者側で許す名前空間ファミリーの記述**であり、
        Realizationの`supports`にワイルドカードを置いてよいという意味ではない。
        要求される**具体的なキー**は各Constructインスタンスで
        `LANGUAGE_ADMISSION.required_contracts(node)`を呼んで確かめる。
        `contracts`に掲載されても、常に全キーが要求されるわけではない。
        """

        title @= "Admission Ruleと契約キーの台帳"
        for _row in baseline_rule_rows():
            obligations @= _row

    class MODES:
        """呼び出しの方式（Composition/Structural）はこの表と独立。
        意味射影のメタデータはArtifactへ自動付加しない。
        """

        title @= "判断表"
        conditions @= (
            "preservation（既定）",
            "Model受理 + supports照合",
            "意味保存を実行検証し、できないケースを拒否",
        )
        conditions @= (
            "projection",
            "Model受理のみ。実行意味のsupports照合なし",
            "抽出対象・保証範囲と誤った射影の拒否をTarget側でテスト",
        )
