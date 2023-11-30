from matplotlib import pyplot as plt
from module.utils import get_or_add
from module.getters import getCompoundAndRatiosDf, getHeadTwitchDf
import seaborn as sns
from statannotations.Annotator import Annotator
from module.constants import COLUMN_ORDER

# from brokenaxis import brokenaxis #REMI or future JAS for quantitaiveSummary() modulenotfound in pip list tho

########## GENERIC HISTOGRAM FUNCTIONS MEANT TO BE USED TO BUILD ANY HISTOGRAM #########

########## HISTOGRAM DATA BUILDERS


def buildHistogramData(  # REMI THIS IS NOT SO GENERIC its better in quantitative - I can not use for behavior at all as no compound or region #TODC
    filename,
    experiment,
    compound,
    region,
):
    compound_and_ratios_df = getCompoundAndRatiosDf(
        filename
    )  # this is not the full ratios df, its only intra region compound ratios for nom
    data = compound_and_ratios_df[
        (compound_and_ratios_df.experiment == experiment)
        & (compound_and_ratios_df.compound == compound)
        & (compound_and_ratios_df.region == region)
    ]

    order = data.sort_values(by="group_id", ascending=True).treatment.unique()
    palette = {
        treatment: color
        for treatment, color in data.groupby(by=["treatment", "color"]).groups.keys()
    }

    return data, order, palette


def buildHeadTwitchHistogramData(
    HT_filename, experiment, vairable  # col to plot i.e. HT_20
):
    HT_df = getHeadTwitchDf(HT_filename)

    data = HT_df[HT_df["experiment"] == experiment].rename(
        columns={vairable: "value"}
    )  # subselect experiment and set vairable col to 'value'

    order = data.sort_values(by="group_id", ascending=True).treatment.unique()
    palette = {
        treatment: color
        for treatment, color in data.groupby(by=["treatment", "color"]).groups.keys()
    }

    return data, order, palette


def buildQuantitativeSummaryHistogramData(
    filename, experiment, histogram_type, to_plot, columns
):
    # subselect and transorm to long format
    compound_and_ratios_df = getCompoundAndRatiosDf(filename)
    value_type = {"compound": "region", "region": "compound"}[histogram_type]

    data = compound_and_ratios_df[
        (compound_and_ratios_df.experiment == experiment)
        & (compound_and_ratios_df[value_type].isin(columns))
        & (compound_and_ratios_df[histogram_type] == to_plot)
    ]  # as to plot will only be one value not list
    # ].query("|".join([f"{histogram_type}=='{value}'" for value in to_plot])) #perhaps this is rewuired for prompt? unsure how to intergrate REMI

    order = sorted(
        columns, key=lambda x: COLUMN_ORDER[value_type].index(x)
    )  # orders regions / compounds as in constants
    hue_order = data.sort_values(by="group_id", ascending=True).treatment.unique()

    hue_palette = {
        treatment: color
        for treatment, color in data.groupby(by=["treatment", "color"]).groups.keys()
    }

    return data, order, hue_order, hue_palette, value_type


########## HISTOGRAM BUILDERS - can it be made more generic and just one? REMI


def buildHistogram(
    title,
    ylabel,
    data,
    order,
    hue=None,
    palette=None,
    swarm_hue=None,
    swarm_palette=None,
    significance_infos=None,  # x='treatment',y='value'
):
    # JASMINE: in what case would the x and y be variables? #REMI we need to talk about this func as it should be more general
    x = "treatment"
    y = "value"

    fig, ax = plt.subplots(figsize=(20, 10))
    ax = sns.barplot(
        x=x,
        y=y,
        data=data,
        hue=hue,
        palette=palette,
        errorbar=("ci", 68),
        order=order,
        capsize=0.1,
        alpha=0.8,
        errcolor=".2",
        edgecolor=".2",
        dodge=False,
    )
    # #REMI so thiis for the outliers! I was trying to have this function work for my other histogram needs but i cant with this
    ax = sns.swarmplot(
        x=x,
        y=y,
        hue=swarm_hue or hue,
        palette=swarm_palette or palette,
        order=order,
        data=data,
        edgecolor="k",
        linewidth=1,
        linestyle="-",
        dodge=False,
        legend=True if swarm_palette else False,
    )

    if significance_infos:
        ax = labelStats(ax, data, x, y, order, significance_infos)

    ax.tick_params(labelsize=24)
    # ax.set_ylabel(ylabel, fontsize=24)
    ax.set_ylabel(ylabel, fontsize=24)
    ax.set_xlabel(" ", fontsize=20)  # treatments
    ax.set_title(title, y=1.04, fontsize=34)  # '+/- 68%CI'
    sns.despine(left=False)
    return fig


def buildHueHistogram(
    title,
    ylabel,
    data,
    order,
    x=None,
    y=None,
    hue=None,
    palette=None,
    hue_order=None,
    significance_infos=None,
):
    fig, ax = plt.subplots(figsize=(20, 10))
    ax = sns.barplot(
        x=x,
        y=y,
        data=data,
        hue=hue,
        palette=palette,
        errorbar=("ci", 68),
        errwidth=1,
        order=order,
        hue_order=hue_order,
        capsize=0.1,
        alpha=0.8,
        errcolor=".2",
        edgecolor=".2",
    )
    ax.set_ylabel(ylabel, fontsize=24)
    ax.set_xlabel(" ", fontsize=20)  # remove x title
    ax.set_title(title, y=1.04, fontsize=34)

    sns.despine(left=False)
    return fig


# TODO pretty sure is saw its possible to have this and the stat test done using special params #JJB: if you mean the seabourn stuff included the stats are too limited and it will not be as required
def labelStats(ax, data, x, y, order, significance_infos):
    pairs, p_values = significance_infos
    annotator = Annotator(ax, pairs, data=data, x=x, y=y, order=order)
    annotator.configure(text_format="star", loc="inside", fontsize="xx-large")
    annotator.set_pvalues_and_annotate(p_values)

    return ax
