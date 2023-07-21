from decimal import Decimal

from cicada.ast.nodes import NumericValue, RecordValue, StringValue, Value
from cicada.ast.types import RecordField, RecordType
from cicada.common.json import asjson
from cicada.domain.triggers import Trigger


def trigger_to_record(trigger: Trigger) -> Value:
    # TODO: optimize

    return json_to_record(asjson(trigger))


# TODO: turn this into a Trigger to Record function
def json_to_record(j: object) -> Value:
    if isinstance(j, dict):
        types = RecordType()
        items: dict[str, Value] = {}

        for k, v in j.items():
            value = json_to_record(v)
            items[k] = value
            types.fields.append(RecordField(k, value.type))

        return RecordValue(items, type=types)

    if isinstance(j, str):
        return StringValue(j)

    if isinstance(j, int | float):
        return NumericValue(Decimal(j))

    raise NotImplementedError()
