# Copyright 2018 New Vector Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from synapse.server import HomeServer

logger = logging.getLogger(__name__)


class DiffWithRefVal(Enum):
    """

    Suppose we're watching an unknown quantity `X` and we're interested if it
    takes on a significant value `v`. For a given observation `x`, either `x == v`
    or `x != v`. Therefore a pair of observations `(x1, x2)` represents one of four
    transitions.

    x1 == v and x2 == v: both match, no change
    x1 != v and x2 != v: neither match, no change
    x1 != v and x2 == v: now matches, changed
    x1 == v and x2 != v: no longer matches, changed
    """

    both_match = auto()
    neither_match = auto()
    now_matches = auto()
    stopped_matching = auto()

    def is_change(self) -> bool:
        return self in (self.now_matches, self.no_longer_matches)


class StateDeltasHandler:
    def __init__(self, hs: "HomeServer"):
        self.store = hs.get_datastore()

    async def _get_key_change(
        self,
        prev_event_id: Optional[str],
        event_id: Optional[str],
        key_name: str,
        public_value: str,
    ) -> DiffWithRefVal:
        """Given two events check if the `key_name` field in content changed
        from not matching `public_value` to doing so.

        For example, check if `history_visibility` (`key_name`) changed from
        `shared` to `world_readable` (`public_value`)."""
        prev_event = None
        event = None
        if prev_event_id:
            prev_event = await self.store.get_event(prev_event_id, allow_none=True)

        if event_id:
            event = await self.store.get_event(event_id, allow_none=True)

        if not event and not prev_event:
            logger.debug("Neither event exists: %r %r", prev_event_id, event_id)
            return DiffWithRefVal.neither_match

        prev_value = None
        value = None

        if prev_event:
            prev_value = prev_event.content.get(key_name)

        if event:
            value = event.content.get(key_name)

        logger.debug("prev_value: %r -> value: %r", prev_value, value)

        if value == public_value:
            if prev_value == public_value:
                return DiffWithRefVal.both_match
            else:
                return DiffWithRefVal.now_matches
        else:
            if prev_value == public_value:
                return DiffWithRefVal.stopped_matching
            else:
                return DiffWithRefVal.neither_match
