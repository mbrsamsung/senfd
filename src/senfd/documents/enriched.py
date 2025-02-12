import inspect
import re
from pathlib import Path
from typing import ClassVar, List, Optional, Tuple, Type, TypeVar

from pydantic import Field

import senfd.models
import senfd.schemas
import senfd.tables
from senfd.documents.base import (
    TRANSLATION_TABLE,
    Converter,
    Document,
    strip_all_suffixes,
)
from senfd.documents.plain import Figure, FigureDocument
from senfd.errors import Error
from senfd.utils import pascal_to_snake

REGEX_ALL = r"(?P<all>.*)"

REGEX_VAL_NUMBER_OPTIONAL = r"(?P<number>\d+)?.*"
REGEX_VAL_HEXSTR = r"^(?P<hex>[a-zA-Z0-9]{1,2}h)$"
REGEX_VAL_NAME = r"^(?P<name>[a-zA-Z -/]*)[ \d]*$"
REGEX_VAL_FIELD_DESCRIPTION = (
    r"(?P<name>[ \/\-\w]+)" r"(\((?P<acronym>[^\)]+)\))?" r"(:\s*(?P<description>.*))?"
)
REGEX_VAL_VALUE_DESCRIPTION = r"(?P<name>[ \w]+)" r"(:\s*(?P<description>.*))?"
REGEX_VAL_REQUIREMENT = r"^(?:(?P<requirement>O|M|P|NR|Note)(?:[ \d]*))?$"
REGEX_VAL_REFERENCE = r"^(?P<reference>\d+\.\d+(?:\.\d+)?(?:\.\d+)?(?:\.\d+)?)$"
REGEX_VAL_YESNO = r"(?P<yn>NOTE|Note|Yes|No|Y|N)[ \d]*?"

REGEX_HDR_EXPLANATION = r"(Definition|Description).*"

REGEX_GRID_RANGE = (
    r"(Bits|Bytes).*",
    r"(?!Note|specficiation)(?:(?P<upper>[0-9 \w\+\*]+):)?(?P<lower>[0-9 \w\+\*]+)",
)
REGEX_GRID_ACRONYM = (r"(Term|Acronym).*", REGEX_ALL.replace("all", "term"))
REGEX_GRID_SCOPE = (
    r"(Scope|Scope.and.Support).*",
    REGEX_ALL.replace("all", "scope"),
)
REGEX_GRID_FIELD_DESCRIPTION = (REGEX_HDR_EXPLANATION, REGEX_VAL_FIELD_DESCRIPTION)
REGEX_GRID_VALUE_DESCRIPTION = (REGEX_HDR_EXPLANATION, REGEX_VAL_VALUE_DESCRIPTION)
REGEX_GRID_EXPLANATION = (
    REGEX_HDR_EXPLANATION,
    REGEX_ALL.replace("all", "description"),
)
REGEX_GRID_FEATURE_NAME = (
    r"(Feature.Name).*",
    REGEX_VAL_NAME.replace("name", "feature_name"),
)
REGEX_GRID_NAME = (
    r".*(Name).*",
    REGEX_VAL_NAME,
)
REGEX_GRID_FEATURE_IDENTIFIER = (
    r"^(Feature|Log Page).Identifier.*",
    REGEX_VAL_HEXSTR.replace("hex", "identifier"),
)
REGEX_GRID_FEATURE_PAPCR = (
    r"(Persistent.Across.Power.Cycle.and.Reset)",
    REGEX_VAL_YESNO.replace("<yn>", "<persist>"),
)
REGEX_GRID_FEATURE_UMBFA = (
    r"(Uses.Memory.Buffer.for.Attributes)",
    REGEX_VAL_YESNO.replace("<yn>", "<membuf>"),
)
REGEX_GRID_REQUIREMENTS = (
    r"^(((:?Command|Feature).+Support.+Requirements)|(:?O\/M)).*$",
    REGEX_VAL_REQUIREMENT,
)
REGEX_GRID_BITS_FUNCTION = (
    r"(Bits|Function).*",
    r"(?P<bitstr>\d{4}\s\d{2}b)",
)
REGEX_GRID_COMMAND_OPCODE = (
    r"(Combined.Opcode|Opcode.Value).*",
    REGEX_VAL_HEXSTR.replace("hex", "opcode"),
)
REGEX_GRID_COMMAND_NAME = (
    r"(Command).*",
    REGEX_VAL_NAME.replace("name", "command_name"),
)
REGEX_GRID_BITS_TRANSFER = (r"(Data.Transfer).*", r"(?P<function>\d{2}b)")
REGEX_GRID_REFERENCE = (
    r"(Reference).*",
    REGEX_ALL.replace("all", "reference"),
)
REGEX_GRID_USES_NSID = (
    r"(Namespace.Identifier.Used|NSID).*",
    REGEX_VAL_YESNO.replace("yn", "uses_nsid"),
)
REGEX_GRID_USES_CNTID = (r"(CNTID).*", REGEX_VAL_YESNO.replace("yn", "uses_cntid"))
REGEX_GRID_USES_CSI = (r"(CSI).*", REGEX_VAL_YESNO.replace("yn", "uses_csi"))
REGEX_GRID_VALUE = (r"(Value).*", REGEX_VAL_HEXSTR.replace("hex", "value"))

REGEX_GRID_TYPE = (r".*(Value|Type).*", REGEX_VAL_HEXSTR.replace("hex", "value"))
REGEX_GRID_TYPE_DESCRIPTION = (
    r".*(Event|Definition|Description).*",
    REGEX_VAL_VALUE_DESCRIPTION,
)

REGEX_GRID_LPI = (
    r"(Log.Page.Identifier).*",
    REGEX_VAL_HEXSTR.replace("hex", "log_page_identifier"),
)
REGEX_GRID_LPN = (r"(Log.Page.Name).*", REGEX_ALL.replace("all", "log_page_name"))
REGEX_GRID_COMMANDS_AFFECTED = (
    r"(Commands.Affected).*",
    REGEX_ALL.replace("all", "comma"),
)
REGEX_GRID_IO = (
    r"(I/O).*",
    REGEX_VAL_REQUIREMENT.replace("requirement", "req_io"),
)
REGEX_GRID_ADMIN = (
    r"(Admin).*",
    REGEX_VAL_REQUIREMENT.replace("requirement", "req_admin"),
)
REGEX_GRID_DISCOVERY = (
    r"(Disc).*",
    REGEX_VAL_REQUIREMENT.replace("requirement", "req_discovery"),
)


class EnrichedFigure(Figure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str]
    REGEX_GRID: ClassVar[List[Tuple]]

    grid: senfd.tables.Grid = Field(default_factory=senfd.tables.Grid)

    def into_document(self, document):
        key = pascal_to_snake(self.__class__.__name__).replace("_figure", "")
        getattr(document, key).append(self)


class DataStructureFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"^(?!.*Status Code|.*Vendor|.*Log.Page.Identifiers|.*Types).*(Log.Page|Data.Structure|Data).*$"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]


class IdentifyDataStructureFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Identify.*Data.Structure.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_RANGE,
        REGEX_GRID_IO,
        REGEX_GRID_ADMIN,
        REGEX_GRID_DISCOVERY,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]


class DataTypeFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r"^.*(Types).*$"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_TYPE,
        REGEX_GRID_TYPE_DESCRIPTION,
    ]


class AcronymsFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Acronym\s+(definitions|Descriptions)"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_ACRONYM,
        REGEX_GRID_EXPLANATION,
    ]


class AsynchronousEventInformationFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"^(Asynchronous.Event.Information.-)(?P<event>.*)$"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_VALUE,
        REGEX_GRID_VALUE_DESCRIPTION,
    ]

    event: str


class IoControllerCommandSetSupportRequirementFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r".*-\s+(?P<command_set_name>.*)Command\s+Set\s+Support"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_COMMAND_NAME,
        REGEX_GRID_REQUIREMENTS,
    ]

    command_set_name: str


class CommandSupportRequirementFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"\s*(?P<command_span>.*)\s+Command\s*Support\s*Requirements.*"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_COMMAND_NAME,
        REGEX_GRID_COMMAND_OPCODE,
        REGEX_GRID_IO,
        REGEX_GRID_ADMIN,
        REGEX_GRID_DISCOVERY,
        REGEX_GRID_REFERENCE,
    ]

    command_span: str


class CnsValueFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*CNS\s+Values.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(CNS.Value).*", REGEX_VAL_HEXSTR.replace("hex", "cns_value")),
        (r"(O\/M).*", REGEX_VAL_REQUIREMENT),
        REGEX_GRID_EXPLANATION,
        REGEX_GRID_USES_NSID,
        REGEX_GRID_USES_CNTID,
        REGEX_GRID_USES_CSI,
        REGEX_GRID_REFERENCE,
    ]


class CommandSqeDataPointerFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+Data\s+Pointer"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]

    command_name: str


class ExampleFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*(Example|example).*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]


class CommandSqeMetadataPointer(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+Metadata\s+Pointer"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]

    command_name: str


class CommandSqeDwordLowerUpperFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s*-\s*Command\s*Dword\s*"
        r"(?P<command_dword_lower>\d+)"
        r".*and.*?\s(?P<command_dword_upper>\d+)$"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]

    command_name: str
    command_dword_lower: int
    command_dword_upper: int


class CommandSqeDwordFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"^(?P<command_name>[-a-zA-Z\w\s\/]+(?:\(\w*\))?)\s*[-–—]\s+"
        r"Command\s*Dword\s*(?P<command_dword>\d+)$"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]

    command_name: str
    command_dword: int


class IdentifyCommandSqeDwordFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"^Command\s*Dword\s*(?P<command_dword>\d+).-.CNS.Specific.Identifier$"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]

    command_name: str = "Identify"
    command_dword: int


class CommandCqeDwordFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+"
        r"Completion\sQueue\sEntry\sDword\s(?P<command_dword>\d+)"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]

    command_name: str
    command_dword: str


class CommandAdminOpcodeFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"Opcodes.for.(?P<command_set_name>Admin).Commands"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_BITS_FUNCTION,
        REGEX_GRID_BITS_TRANSFER,
        REGEX_GRID_COMMAND_OPCODE,
        REGEX_GRID_USES_NSID,
        REGEX_GRID_COMMAND_NAME,
        REGEX_GRID_REFERENCE,
    ]

    command_set_name: str


class CommandIoOpcodeFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"Opcodes\sfor\s(?P<command_set_name>.*?)"
        r"\s(Commands|Command Set|Command Set Commands)"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_BITS_FUNCTION,
        REGEX_GRID_BITS_TRANSFER,
        REGEX_GRID_COMMAND_OPCODE,
        REGEX_GRID_COMMAND_NAME,
        REGEX_GRID_REFERENCE,
    ]

    command_set_name: str


class GeneralCommandStatusValueFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*General.Command.Status.Values.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_VALUE,
        REGEX_GRID_VALUE_DESCRIPTION,
        REGEX_GRID_COMMANDS_AFFECTED,
    ]


class GenericCommandStatusValueFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[a-zA-Z -/]*).-.Generic.Command.Status.Values.*"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_VALUE,
        REGEX_GRID_VALUE_DESCRIPTION,
    ]


class CommandSpecificStatusValueFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"(?P<command_name>[\w\s]+)\s+-\s+Command\s+Specific\s+Status\s+Values"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_VALUE,
        REGEX_GRID_VALUE_DESCRIPTION,
        REGEX_GRID_COMMANDS_AFFECTED,
    ]
    command_name: str


class FeatureIdentifierFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Feature\s*Identifiers.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_FEATURE_IDENTIFIER,
        REGEX_GRID_FEATURE_PAPCR,
        REGEX_GRID_FEATURE_UMBFA,
        REGEX_GRID_EXPLANATION,
        REGEX_GRID_SCOPE,
    ]


class VersionDescriptorFieldValueFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r"^.*Version Descriptor Field Values$"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(Specification.Version.).*", r"^(?P<version>\d\.\d)$"),
        (r"(MJR.Field).*", REGEX_VAL_HEXSTR.replace("hex", "version_major")),
        (r"(MNR.Field).*", REGEX_VAL_HEXSTR.replace("hex", "version_minor")),
        (r"(TER.Field).*", REGEX_VAL_HEXSTR.replace("hex", "version_tertiary")),
    ]


class HostSoftwareSpecifiedFieldFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r"^.*-.Host Software Specified Fields$"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]


class FeatureSupportFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r"^I.O.Controller.-.Feature.Support$"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_FEATURE_NAME,
        REGEX_GRID_REQUIREMENTS,
    ]


class LogPageIdentifierFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Log\s+Page\s+Identifiers.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_LPI,
        REGEX_GRID_SCOPE,
        REGEX_GRID_LPN,
        REGEX_GRID_REFERENCE,
    ]


class OffsetFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*offset"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        (r"(Type).*", REGEX_ALL),
        (r"(Reset).*", REGEX_VAL_HEXSTR.replace("hex", "reset")),
        REGEX_GRID_EXPLANATION,
    ]


class ParameterFieldFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r"^.*(Parameter.Field)$"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]


class SubmissionQueueFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*(Submission.Queue.Entry).*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]


class DescriptorFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r"^.*(Descriptor)$"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]


class CompletionQueueFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"^(?:Fabrics.Response.-)?(Completion.Queue).*$"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]


class PropertyDefinitionFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r".*Property Definition.*"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        (r"(Offset.\(OFST\)).*", REGEX_VAL_HEXSTR),
        (r"(Size.\(in.bytes\)).*", REGEX_VAL_NUMBER_OPTIONAL),
        (
            r"(I/O Controller).*",
            REGEX_VAL_REQUIREMENT.replace("requirement", "req_ioc"),
        ),
        (
            r"(Administrative.Controller).*",
            REGEX_VAL_REQUIREMENT.replace("requirement", "req_ac"),
        ),
        (
            r"(Discovery.Controller).*",
            REGEX_VAL_REQUIREMENT.replace("requirement", "req_dc"),
        ),
        (r"(Name).*", REGEX_VAL_FIELD_DESCRIPTION),
    ]


class StatusCodeFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r"^(Status.Code.-).*$"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_VALUE,
        REGEX_GRID_VALUE_DESCRIPTION,
    ]


class StatusValueFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r"^.*(Status.Value).*$"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_VALUE,
        REGEX_GRID_VALUE_DESCRIPTION,
    ]


class FormatFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = (
        r"^(?!.*IEEE|Sanitize.Operations).*\s(Format).*$"
    )
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_RANGE,
        REGEX_GRID_FIELD_DESCRIPTION,
    ]


class RequirementsFigure(EnrichedFigure):
    REGEX_FIGURE_DESCRIPTION: ClassVar[str] = r"^.*(Requirements)$"
    REGEX_GRID: ClassVar[List[Tuple]] = [
        REGEX_GRID_NAME,
        REGEX_GRID_FEATURE_IDENTIFIER,
        REGEX_GRID_IO,
        REGEX_GRID_ADMIN,
        REGEX_GRID_DISCOVERY,
        REGEX_GRID_REFERENCE,
    ]


class EnrichedFigureDocument(Document):
    SUFFIX_JSON: ClassVar[str] = ".enriched.figure.document.json"
    SUFFIX_HTML: ClassVar[str] = ".enriched.figure.document.html"

    FILENAME_SCHEMA: ClassVar[str] = "enriched.figure.document.schema.json"
    FILENAME_HTML_TEMPLATE: ClassVar[str] = "enriched.figure.document.html.jinja2"

    acronyms: List[AcronymsFigure] = Field(default_factory=list)
    data_structure: List[DataStructureFigure] = Field(default_factory=list)
    example: List[ExampleFigure] = Field(default_factory=list)
    io_controller_command_set_support_requirement: List[
        IoControllerCommandSetSupportRequirementFigure
    ] = Field(default_factory=list)
    command_admin_opcode: List[CommandAdminOpcodeFigure] = Field(default_factory=list)
    command_io_opcode: List[CommandIoOpcodeFigure] = Field(default_factory=list)
    command_support_requirement: List[CommandSupportRequirementFigure] = Field(
        default_factory=list
    )
    identify_data_structure: List[IdentifyDataStructureFigure] = Field(
        default_factory=list
    )
    identify_command_sqe_dword: List[IdentifyCommandSqeDwordFigure] = Field(
        default_factory=list
    )
    command_sqe_dword: List[CommandSqeDwordFigure] = Field(default_factory=list)
    command_sqe_dword_lower_upper: List[CommandSqeDwordLowerUpperFigure] = Field(
        default_factory=list
    )
    command_sqe_data_pointer: List[CommandSqeDataPointerFigure] = Field(
        default_factory=list
    )
    command_sqe_metadata_pointer: List[CommandSqeMetadataPointer] = Field(
        default_factory=list
    )
    command_cqe_dword: List[CommandCqeDwordFigure] = Field(default_factory=list)
    command_specific_status_value: List[CommandSpecificStatusValueFigure] = Field(
        default_factory=list
    )
    general_command_status_value: List[GeneralCommandStatusValueFigure] = Field(
        default_factory=list
    )
    generic_command_status_value: List[GenericCommandStatusValueFigure] = Field(
        default_factory=list
    )
    cns_value: List[CnsValueFigure] = Field(default_factory=list)
    feature_support: List[FeatureSupportFigure] = Field(default_factory=list)
    feature_identifier: List[FeatureIdentifierFigure] = Field(default_factory=list)
    log_page_identifier: List[LogPageIdentifierFigure] = Field(default_factory=list)
    offset: List[OffsetFigure] = Field(default_factory=list)
    property_definition: List[PropertyDefinitionFigure] = Field(default_factory=list)
    descriptor: List[DescriptorFigure] = Field(default_factory=list)
    completion_queue: List[CompletionQueueFigure] = Field(default_factory=list)
    parameter_field: List[ParameterFieldFigure] = Field(default_factory=list)
    submission_queue: List[SubmissionQueueFigure] = Field(default_factory=list)
    status_code: List[StatusCodeFigure] = Field(default_factory=list)
    status_value: List[StatusValueFigure] = Field(default_factory=list)
    format: List[FormatFigure] = Field(default_factory=list)
    asynchronous_event_information: List[AsynchronousEventInformationFigure] = Field(
        default_factory=list
    )
    requirements: List[RequirementsFigure] = Field(default_factory=list)

    data_type: List[DataTypeFigure] = Field(default_factory=list)
    version_descriptor_field_value: List[VersionDescriptorFieldValueFigure] = Field(
        default_factory=list
    )

    host_software_specified_field: List[HostSoftwareSpecifiedFieldFigure] = Field(
        default_factory=list
    )

    nontabular: List[Figure] = Field(default_factory=list)
    uncategorized: List[Figure] = Field(default_factory=list)


# EnrichedFigureType is a virtual type that binds to `EnrichedFigure` such
# that it enforces that `EnrichedFigureType` needs to be a child of `EnrichedFigure`
EnrichedFigureType = TypeVar("EnrichedFigureType", bound=EnrichedFigure)


class FromFigureDocument(Converter):
    """
    Constructs an EnrichedDocument from a given PlainDocument

    Figures are enriched by extraction, type coercion, and conversion of using data from
    the figure description and table content.
    """

    @staticmethod
    def is_applicable(path: Path) -> bool:
        return "".join(path.suffixes).lower() == ".plain.figure.document.json"

    @staticmethod
    def check_regex(figure, match) -> List[senfd.errors.Error]:
        shared = set(figure.model_dump().keys()).intersection(
            set(match.groupdict().keys())
        )
        if shared:
            return [
                senfd.errors.ImplementationError(
                    message=f"cls({figure.__class__.__name__}) has overlap({shared})"
                )
            ]

        return []

    @staticmethod
    def check_table_data(
        figure: EnrichedFigure,
    ) -> Tuple[Optional[senfd.errors.Error], List[senfd.errors.Error]]:
        """Check for blocking errors, for which enrichment cannot continue"""

        if figure.table is None:
            return (
                senfd.errors.FigureTableMissingError(
                    figure_nr=figure.figure_nr, message="Missing table"
                ),
                [],
            )
        if len(figure.table.rows) < 2:
            return (
                senfd.errors.FigureTableMissingRowsError(
                    figure_nr=figure.figure_nr, message=r"Number of rows < 2"
                ),
                [],
            )

        lengths = list(set([len(row.cells) for row in figure.table.rows]))
        if len(lengths) != 1:
            return None, [
                senfd.errors.IrregularTableError(
                    figure_nr=figure.figure_nr,
                    message=f"Varying row lengths({lengths})",
                    lengths=lengths,
                )
            ]

        return None, []

    @staticmethod
    def check_grid(figure: EnrichedFigure) -> List[senfd.errors.Error]:
        """
        Checks the state of the grid, assuming state after enrichment, thus expecting
        the grid to contain headers, fields, and value. Returning error(s) if it does
        not.
        """

        errors: List[senfd.errors.Error] = []

        if not figure.grid.headers:
            errors.append(
                senfd.errors.FigureNoGridHeaders(
                    figure_nr=figure.figure_nr,
                    message=(
                        "Grid is missing headers;"
                        f" check {figure.__class__.__name__}.REGEX_GRID"
                    ),
                )
            )

        if not figure.grid.fields:
            errors.append(
                senfd.errors.FigureNoGridHeaders(
                    figure_nr=figure.figure_nr,
                    message=(
                        "Grid is missing fields;"
                        f" check {figure.__class__.__name__}.REGEX_GRID"
                    ),
                )
            )

        if not figure.grid.values:
            errors.append(
                senfd.errors.FigureNoGridValues(
                    figure_nr=figure.figure_nr,
                    message=(
                        "Grid is missing values;"
                        f" check {figure.__class__.__name__}.REGEX_GRID"
                    ),
                )
            )

        return errors

    @staticmethod
    def enrich(
        cls: Type[EnrichedFigureType], figure: Figure, match: re.Match
    ) -> Tuple[Optional[EnrichedFigure], List[Error]]:
        """Returns an EnrichedFigure from the given Figure"""

        errors: List[Error] = []

        # Merge figure data with fields from regex
        data = figure.model_dump()
        mdict = match.groupdict()
        if mdict:
            data.update(mdict if mdict else {})

        enriched: EnrichedFigure = cls(**data)

        # Check for non-blocking error-conditions
        errors += FromFigureDocument.check_regex(enriched, match)
        error, non_blocking = FromFigureDocument.check_table_data(enriched)
        errors += non_blocking
        if error:
            errors.append(error)
            return None, errors

        regex_hdr, regex_val = zip(*enriched.REGEX_GRID)

        header_names: List[str] = []

        fields: List[str] = []
        values: List[List[str | int]] = []
        assert enriched.table
        for row_idx, row in enumerate(enriched.table.rows[1:], 1):
            if not header_names:
                header_matches = [
                    header_match.group(1) if header_match else header_match
                    for header_match in (
                        re.match(regex, cell.text.strip().replace("\n", " "))
                        for cell, regex in zip(row.cells, regex_hdr)
                    )
                ]
                if all(header_matches):
                    header_names = [str(hdr) for hdr in header_matches]
                else:
                    mismatches = [
                        (
                            idx,
                            regex_hdr[idx],
                            row.cells[idx].text.strip().replace("\n", " "),
                        )
                        for idx, hdr in enumerate(header_matches)
                        if not hdr
                    ]
                    errors.append(
                        senfd.errors.FigureTableRowError(
                            figure_nr=enriched.figure_nr,
                            table_nr=enriched.table.table_nr,
                            row_idx=row_idx,
                            message=f"No match REGEX_GRID/Headers on idx({mismatches})",
                        )
                    )
                continue

            combined = {}
            value_errors: List[Error] = []
            for cell_idx, (cell, regex) in enumerate(zip(row.cells, regex_val)):
                text = cell.text.strip().translate(TRANSLATION_TABLE)
                match = re.match(regex, text)  # type: ignore
                if match:
                    combined.update(match.groupdict())
                    continue

                value_errors.append(
                    senfd.errors.FigureTableRowCellError(
                        figure_nr=enriched.figure_nr,
                        table_nr=enriched.table.table_nr,
                        row_idx=row_idx,
                        cell_idx=cell_idx,
                        message=f"cell.text({text}) no match({regex})",
                    )
                )

            if value_errors:
                errors += value_errors
                continue

            cur_fields = list(combined.keys())
            if not fields:
                fields = cur_fields

            diff = list(set(cur_fields).difference(set(fields)))
            if diff:
                errors.append(
                    senfd.errors.FigureTableRowError(
                        figure_nr=enriched.figure_nr,
                        table_nr=enriched.table.table_nr,
                        row_idx=row_idx,
                        message=f"Unexpected fields ({fields}) != ({cur_fields})",
                    )
                )
                continue

            values.append(list(combined.values()))

        data = enriched.table.dict()
        data["headers"] = header_names
        data["fields"] = fields
        data["values"] = values

        enriched.grid = senfd.tables.Grid(**data)

        errors += FromFigureDocument.check_grid(enriched)

        return enriched, errors

    @staticmethod
    def get_figure_enriching_classes():
        """
        To avoid manually crafting a list of classes, this function
        introspectively examines this module for applicable
        classes with "REGEX_FIGURE_DESCRIPTION" class attribute.
        """
        return [
            cls
            for _, cls in inspect.getmembers(senfd.documents.enriched, inspect.isclass)
            if issubclass(cls, EnrichedFigure)
            and (cls is not senfd.documents.enriched.EnrichedFigure)
            and hasattr(cls, "REGEX_FIGURE_DESCRIPTION")
        ]

    @staticmethod
    def convert(path: Path) -> Tuple[Document, List[Error]]:
        """Instantiate an 'organized' Document from a 'figure' document"""

        errors = []

        figure_document = FigureDocument.model_validate_json(path.read_text())

        document = EnrichedFigureDocument()
        document.meta.stem = strip_all_suffixes(path.stem)

        figure_organizers = FromFigureDocument.get_figure_enriching_classes()
        for figure in figure_document.figures:
            if not figure.table:
                document.nontabular.append(figure)
                continue

            match = None
            description = figure.description.translate(TRANSLATION_TABLE)
            for candidate in figure_organizers:
                match = re.match(
                    candidate.REGEX_FIGURE_DESCRIPTION, description, flags=re.IGNORECASE
                )
                if match:
                    enriched, conv_errors = FromFigureDocument.enrich(
                        candidate, figure, match
                    )
                    errors += conv_errors
                    if not enriched:
                        break
                    enriched.into_document(document)
                    break

            if not match:
                document.uncategorized.append(figure)

        return document, errors
