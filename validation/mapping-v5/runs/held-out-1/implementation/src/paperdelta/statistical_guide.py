"""Explicit statistical conventions shared by the terminal guides."""

from paperdelta.i18n import tr


def contract_questions(questions):
    ddof = questions.choose(
        "statistics.guide_ddof",
        [(1, tr("statistics.sample_sd")), (0, tr("statistics.population_sd"))],
    )
    unit = questions.read("statistics.guide_unit", required=True)
    interval = None
    if ddof == 1 and questions.choose(
        "statistics.guide_ci", [(False, tr("guide.no")), (True, tr("guide.yes"))]
    ):
        level = questions.read("statistics.guide_level", required=True)
        questions.choose("statistics.assumption", [(True, tr("statistics.assumption_accept"))])
        interval = {
            "method": "student_t",
            "level": level,
            "assumption": "independent_normal_observations",
        }
    return {"ddof": ddof, "unit_of_analysis": unit, "confidence_interval": interval}


def display_questions(questions):
    component = questions.choose(
        "statistics.guide_display",
        [
            (key, tr("statistics.component_" + key))
            for key in [
                "mean",
                "sd",
                "se",
                "n",
                "ci_lower",
                "ci_upper",
                "confidence_level",
                "mean_sd",
                "mean_se",
                "ci",
                "mean_ci",
            ]
        ],
    )
    compound = component in {"mean_sd", "mean_se", "ci", "mean_ci"}
    show_n = compound and questions.choose(
        "statistics.guide_n", [(False, tr("guide.no")), (True, tr("guide.yes"))]
    )
    if compound:
        questions.output.write(tr("statistics.selection") + "\n")
    return {"component": component, "show_n": show_n}
