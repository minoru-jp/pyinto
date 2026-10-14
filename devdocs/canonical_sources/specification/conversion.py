"""Public conversion API independent of the Model."""

from shikumi_devdoc.fields.specification import MUST, level, related
from shikumi_devdoc.norms.common import canonical_source, summary
from shikumi_devdoc.norms.document import title

from devdocs.canonical_sources.specification.construct import (
    SPECIFICATION_PART as CONSTRUCT_SPEC,
)


@summary("明示された実現規則を使う、Model 外の Python 変換入口。")
@canonical_source(
    "Conversion API",
    filename="conversion.md",
    order=40,
    merge_policy="local",
    heading="identity",
)
class SPECIFICATION_PART:
    """初期の公開 Python API。CLI / Cartridge 自動発見は未実装。"""

    class CVT_001:
        """`pyinto.convert(source, *, realizations, interface_mappings=None, admission=None)` は Python ソース文字列を受け、`PythonFrontend` で正規化した後、指定された `RealizationRegistry` とTarget専用Artifact Sessionで実現し、Sessionが提出した成果物オブジェクトをそのまま返す。Target の推測・暗黙の C 選択は行わない。Construct 提供者の `AdmissionRegistry` は明示された `admission` を優先し、未指定なら明示された `InterfaceMappingRegistry` の契約登録を利用する。"""

        title @= "ソースからの共通変換入口"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_006,)

    class CVT_002:
        """`pyinto.realize(program, *, realizations, admission=None)` は既存の Construct Tree を変更せず、渡された `RealizationRegistry` で選択・実現し、Targetが提出した任意型の成果物を返す。同じ Program を異なる Registry で繰り返し実現できる。`admission` を指定しない場合は Language Construct の契約登録だけを用いる。外部Constructは提供者登録を明示的に渡さない限り拒否する。"""

        title @= "既存 Model の任意 Realization"
        level @= MUST
        related @= (CONSTRUCT_SPEC.CST_001,)

    class CVT_003:
        """`realizations` に `RealizationRegistry` 以外を渡した場合、または `realize` に Construct 以外を渡した場合は TypeError とし、未知の Construct・未対応 Target 操作は既存の `ConstructError` として明示的に失敗する。登録された外部Interface Mappingが必要な場合、呼び出し側が `interface_mappings=` を明示して渡す。`admission` に不正な型を渡した場合も TypeError とする。未登録 Construct は Target のレシピがあっても拒否し、既存Language Construct契約の上書きを許さない。現在はTarget ImplementationやInterfaceの自動探索・解決を行わない。"""

        title @= "依存の明示と失敗"
        level @= MUST

    class CVT_004:
        """`realize`と`convert`の成果物返却型は`object`であり、Hostは文字列化・ファイル保存・最終テキスト結合を行わない。Target Implementationが変換要求ごとに生成するSessionの`finish()`結果を返す。Compositionでは既存Layoutを`accept_composition(layout, context)`でSessionへ渡し、最終描画はTargetが選んだ実装で行う。Structuralでは全Constructの`visit(node, ctx)`を処理した後に提出を要求する。失敗時は`finish()`を呼ばず、次の変換で状態を再利用しない。"""

        title @= "Target所有の成果物と提出ライフサイクル"
        level @= MUST
