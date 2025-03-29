from packaging.requirements import InvalidRequirement, Requirement

from pipzap.exceptions import ParsingError


def parse_requirement_string(requirement_string: str) -> Requirement:
    """Attempts to parse a PEP 508 requirement string into a packaging object,
    wrapping the exceptions.

    Args:
        requirement_string: PEP 508 requirement string to parse. May include markers.

    Raises:
        ParsingError: If a malformed (or otherwise invalid) requirement is provided.

    Returns:
        A parsed `Requirement` object.
    """
    try:
        return Requirement(requirement_string)

    except InvalidRequirement as e:
        raise ParsingError(f"Malformed dependency '{requirement_string}': {e}") from e

    except Exception as e:
        raise ParsingError(f"Unable to parse dependency '{requirement_string}': {e}") from e
