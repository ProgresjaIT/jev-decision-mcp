import logging

from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy


class TypeSafeProvider:
    def __init__(self, settings):
        self.settings = settings
        # SDK debug logging can contain complete customer state.
        logging.getLogger("typesafe_sdk").disabled = True

    async def evaluate(self, state, questions):
        async with AsyncTypeSafeClient(
            api_key=self.settings.typesafe_api_key.get_secret_value(),
            model=self.settings.model,
            base_url="https://api.typesafe.ai",
            retry=RetryPolicy(max_retries=0),
            timeout=self.settings.timeout_seconds,
            compression=False,
        ) as client:
            response = await client.system_one(state=state, questions=questions)
            return response.model_dump(mode="json")
