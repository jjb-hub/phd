from dataclasses import dataclass, field
from typing import get_args
from module.core.FileSystem import FileSystem
from module.core.Metadata import ProjectInformation, TreatmentInformation, ExperimentInformation
from module.core.HPLC import HPLC
from module.core.Outliers import Outliers
from module.core.utils import is_array_like
import matplotlib.pyplot as plt
import seaborn as sns
from module.core.questions import input_list, yes_or_no



def convert_parameter_to_list(parameter):
    if parameter is None:
        raise ValueError("None should be handled specifically")
    if isinstance(parameter, str):
        return parameter.replace(", ", ",").replace(" ,", "").split(",")
    elif is_array_like(parameter):
        return list(parameter)
    return [parameter]


def whisker_plot(data, grouping):
    swarm_palette = {
        "normal": "green",
        "eliminated": "red",
        "kept": "blue",
    }

    EXTRA_COLORS = [
        "red",
        "orange",
        "yellow",
        "pink",
        "purple",
        "brown",
    ]

    for hue in data.palette_hue.unique():
        if "suspected" in hue:
            swarm_palette[hue] = EXTRA_COLORS.pop(0)

    ax = sns.boxplot(y="value", data=data, dodge=False)
    sns.swarmplot(
        ax=ax,
        y="value",
        data=data,
        hue="palette_hue",
        size=5,
        palette=swarm_palette,
        dodge=False,
        edgecolor="k",
        linewidth=1,
    )
    ax.set_title(grouping)
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.tight_layout()
    plt.show()


def handle_outlier_selection(title, data):
    finished = False
    while not finished:
        data["palette_hue"] = data.apply(
            lambda row: (
                f"suspected (mouse_id={row.mouse_id})"
                if row.outlier_status == "suspected"
                else row.outlier_status
            ),
            axis=1,
        )
        whisker_plot(data, title)
        eliminated = input_list(
            f"Select outliers for {title}: input mouse_ids to eliminated or write 'none'"
        )
        
        def label_eliminated(row):
            if row.is_outlier:
                return (
                    "eliminated"
                    if str(row.mouse_id) in eliminated
                    else "kept"
                )
            return row.outlier_status
        
        data.palette_hue = data.apply(label_eliminated, axis=1)
        whisker_plot(data, title)
        finished = yes_or_no("Confirm selection?")
    return data.palette_hue


@dataclass
class DataSelection:

    project: str | list = field(kw_only=True)
    experiment: str = field(kw_only=True, default=None)
    compound: str | list = field(kw_only=True, default=None)
    region: str | list = field(kw_only=True, default=None)
    remove_outliers: str | bool = field(kw_only=True, default=None)
    p_value_threshold: float = field(kw_only=True, default=None)

    def __post_init__(self):
        if self.project not in FileSystem.list_projects():
            raise ValueError(f"Unknown project {self.project}")
        
        self.project_information = ProjectInformation(self.project)
        self.treatment_information = TreatmentInformation(self.project)
        self.experiment_information = ExperimentInformation(self.project)
        
        self.p_value_threshold = self.p_value_threshold or self.project_information.p_value_threshold

        self.data = (
            HPLC(self.project)
            .extend(self.treatment_information)
            .extend(Outliers(self.project))
        )

        self.experiment_options = self.experiment_information.experiments
        self.compound_options = self.data.compound.unique()
        self.region_options = self.data.region.unique()
        self.remove_outliers_options = ["calculated", "eliminated", False]
        
        for name in ["experiment", "compound", "region"]:
            options = getattr(self, name + "_options")
            if getattr(self, name) is not None:
                processed_parameter = self.process_parameter(name, options)
                setattr(self, name, processed_parameter)
            if is_array_like(getattr(self, name)) and len(getattr(self, name)) == 1:
                setattr(self, name, getattr(self, name)[0])
        
        self.data = self.data.select(compound=self.compound, region=self.region)
        
        if self.experiment:
            self.experiment_information = self.experiment_information.select(label=self.experiment)
            
            self.data = self.data.select(
                group_id=self.experiment_information.groups
            )
        
        self.treatments = list(set(self.treatment_information.label).intersection(self.data.treatment.unique()))
                    
        if self.remove_outliers == "eliminated":
            self.process_outliers()
            self.data = self.data.select(outlier_status=["normal", "kept"])
        elif self.remove_outliers == "calculated":
            self.data = self.data.select(is_outlier=False)

        self.data = self.data.select(value='notna')

    def process_parameter(self, name, options):
        parameter = getattr(self, name)
        parameter_field = self.__dataclass_fields__[name]
        if not isinstance(parameter, parameter_field.type):
            raise ValueError(f"{name} must be of type {parameter_field.type}")
        parameter_to_list = convert_parameter_to_list(parameter)
        unknown_params = set(parameter_to_list) - set(options)
        if unknown_params:
            raise ValueError(f"Invalid parameter(s) for {name}: {unknown_params}")
        return parameter_to_list

    def process_outliers(self):
        for (treatment, compound, region), data in self.data.groupby(
            ["treatment", "compound", "region"]
        ):
            if "suspected" in data.outlier_status.values:
                title = f"{compound} in {region} for {treatment}"
                data.outlier_status = handle_outlier_selection(title, data)
                Outliers(self.project).update(data)
