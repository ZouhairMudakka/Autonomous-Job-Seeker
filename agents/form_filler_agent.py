"""
Form Filling Agent (Async, Playwright) - GPT-4o Cover Letter Integration

Enhancements:
1. Cover letter generation using GPT-4o.
2. Retry logic (once) if cover letter generation fails.
3. Required answers must be supplied explicitly; failed generation stops that field.
4. Delays adjusted to a shorter range, can be easily tweaked.

Usage Example:
--------------
form_data = {
    "full_name": "Alice Wonderland",
    "gender": "female",
    "cv_file": "/path/to/resume.pdf",
    "cover_letter": {
        "job_title": "Data Scientist",
        "job_description": "Looking for a DS with Python & ML experience."
    }
}

form_mapping = {
    "full_name": {"selector": "#name-input", "type": "text"},
    "gender": {"selector": "input[name='gender']", "type": "radio"},
    "cv_file": {"selector": "input[type='file']", "type": "upload"},
    "cover_letter": {
        "selector": "textarea[name='cover_letter']",
        "type": "cover_letter_text",
        "required": True  # indicates it's mandatory
    }
}
"""

import asyncio
import random
import os
import json
import tempfile
from typing import Any, Dict, Union, Optional
from pathlib import Path

import openai
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from constants import TimingConstants, Selectors, Messages
from utils.telemetry import TelemetryManager
from utils.dom.dom_service import DomService
from storage.logs_manager import LogsManager
from locators.linkedin_locators import LinkedInLocators

class FormFillerAgent:
    def __init__(self, dom_service: DomService, logs_manager: LogsManager, settings: dict = None):
        """Initialize form filler with DOM service and settings."""
        self.dom_service = dom_service
        self.settings = settings or {}
        self.telemetry = TelemetryManager(self.settings)
        self.logs_manager = logs_manager

        # Standard delays
        self.human_delay_min = 0.3  # seconds
        self.human_delay_max = 1.0  # seconds
        self.action_delay = 2.0     # seconds (for form submissions)
        self.transition_delay = 3.0 # seconds (for page transitions)
        self.poll_interval = 0.5    # seconds (for condition checks)

        self.default_wait = 10.0  # seconds
        self.raise_on_error = False

    async def fill_form(self, form_data: Dict[str, Any], form_mapping: Dict[str, Dict[str, Any]]) -> bool:
        """
        Fill a form using provided data and field mapping.

        If a mapping entry includes {"required": True}, we treat that field as mandatory.
        For example:
          "cover_letter": {"selector": "textarea[name='cover_letter']", "type": "cover_letter_text", "required": True}
        """
        success = True
        for field_name, config in form_mapping.items():
            if config.get("required") and (field_name not in form_data or form_data[field_name] is None or form_data[field_name] == ""):
                await self.logs_manager.error(f"Required field '{field_name}' has no supplied value")
                success = False

        for field_name, field_value in form_data.items():
            if field_name not in form_mapping:
                await self.logs_manager.warning(f"No mapping for field '{field_name}', skipping.")
                continue

            config = form_mapping[field_name]
            selector = config["selector"]
            field_type = config.get("type", "text")
            required = config.get("required", False)  # whether the field is mandatory

            try:
                await self.logs_manager.debug(f"Filling field '{field_name}' of type '{field_type}'")
                await self._fill_field(field_name, field_value, selector, field_type, required)
                await asyncio.sleep(TimingConstants.FORM_FIELD_DELAY / 1000)  # Delay between fields
            except Exception as e:
                error_msg = f"Error filling field '{field_name}': {str(e)}"
                await self.logs_manager.error(error_msg)
                success = False
                if self.raise_on_error:
                    raise Exception(error_msg)

        await self.telemetry.track_event("form_filling", {"form_type": form_data.get("type", "application")}, success=success)
        return success

    async def submit_form(self, submit_button_selector: str, success_selector: str = None) -> bool:
        """
        Click the submit button and return True only after a confirmation appears.

        Raises an exception if not found and raise_on_error=True.
        """
        await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN / 1000)  # Delay before submission
        try:
            success_selector = success_selector or ", ".join(LinkedInLocators.FORM_SUCCESS)
            existing = await self.dom_service.query_selector(success_selector)
            if existing is not None and await existing.is_visible():
                await self.logs_manager.warning("A prior application confirmation is still visible; refusing an ambiguous submission")
                return False
            await self.logs_manager.info("Attempting to submit form...")
            element = await self._wait_for_element(submit_button_selector)
            await element.click()
            await asyncio.sleep(TimingConstants.FORM_SUBMIT_DELAY / 1000)  # Delay after submission
            confirmation = await self.dom_service.wait_for_selector(success_selector, timeout=TimingConstants.DEFAULT_TIMEOUT)
            if confirmation is None:
                await self.logs_manager.warning("Submission was clicked but no application confirmation appeared")
                return False
            await self.logs_manager.info("Form submission confirmed")
            return True
        except Exception as e:
            error_msg = f"Could not submit form: {str(e)}"
            await self.logs_manager.error(error_msg)
            if self.raise_on_error:
                raise Exception(error_msg)
            return False

    async def fill_easy_apply(self, form_data: Dict[str, Any] = None) -> str:
        """
        Specialized method for LinkedIn's Easy Apply flow.
        Handles multi-step forms including CV upload, text fields, and radio/checkbox options.

        Args:
            form_data: Optional dict with pre-filled data like:
                {
                    "phone": "1234567890",
                    "cv_path": "/path/to/resume.pdf",
                    "work_authorization": "Yes",
                    "years_of_experience": "3-5 years"
                }
        Returns:
            str: "applied", "failed", or "skipped"
        """
        try:
            form_data = form_data or {}
            await self.logs_manager.info("Starting LinkedIn Easy Apply process...")

            # Step 2: Process each form step until submission
            max_steps = max(1, int(self.settings.get("max_application_steps", 10)))
            for _ in range(max_steps):
                # Uploads and required questions can appear on any step, including the last.
                if not await self._handle_cv_upload(form_data.get("cv_path")):
                    return "failed"
                if not await self._fill_current_step_fields(form_data):
                    return "skipped"
                # Check for final submit button first
                submit_btn = await self.dom_service.query_selector('button[aria-label="Submit application"]')
                if submit_btn:
                    confirmed = await self.submit_form('button[aria-label="Submit application"]')
                    return "applied" if confirmed else "failed"

                # Look for and click "Next" button
                next_btn = await self.dom_service.query_selector('button[aria-label="Continue to next step"], button[aria-label="Review your application"]')
                if next_btn:
                    await self.logs_manager.debug("Moving to next form step...")
                    await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN / 1000)
                    await next_btn.click()
                    await asyncio.sleep(TimingConstants.ACTION_DELAY / 1000)
                    if await self.dom_service.query_selector(Selectors.LINKEDIN_FORM_ERROR):
                        await self.logs_manager.warning("Application has validation errors; stopping")
                        return "failed"
                else:
                    await self.logs_manager.warning("No next or submit button found")
                    return "failed"
            await self.logs_manager.warning("Application exceeded the maximum number of form steps")
            return "failed"

        except Exception as e:
            await self.logs_manager.error(f"Easy Apply form filling failed: {e}")
            return "failed"

    async def _handle_cv_upload(self, cv_path: Optional[str]) -> bool:
        """Handle CV upload if required and CV path is provided."""
        try:
            upload_input = await self.dom_service.query_selector('input[type="file"][name="fileId"]')
            if upload_input:
                if cv_path:
                    if not Path(cv_path).is_file():
                        return False
                    await self.logs_manager.info("Uploading CV")
                    await upload_input.set_input_files(str(cv_path))
                    await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY / 1000)
                    await self.logs_manager.info("CV upload completed")
                else:
                    if await upload_input.get_attribute("required") is not None:
                        await self.logs_manager.warning("CV upload required but no CV path provided")
                        return False
            return True
        except Exception as e:
            await self.logs_manager.error(f"CV upload failed: {e}")
            return False

    async def _fill_current_step_fields(self, form_data: Dict[str, Any]) -> bool:
        """
        Fill all visible fields in the current step of the Easy Apply form.
        Handles common LinkedIn form field types.
        """
        try:
            await self.logs_manager.debug("Processing current form step fields...")
            # Phone number field
            phone_input = await self.dom_service.query_selector('input[name="phoneNumber"]')
            if phone_input and form_data.get("phone"):
                await self.logs_manager.debug("Filling phone number field")
                await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN / 1000)
                await phone_input.fill(form_data["phone"])

            # Work authorization radio buttons
            if form_data.get("work_authorization"):
                await self.logs_manager.debug("Setting work authorization")
                auth_radio = await self.dom_service.query_selector(
                    f'input[name="work_authorization"][value={json.dumps(str(form_data["work_authorization"]))}]'
                )
                if auth_radio:
                    await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN / 1000)
                    await auth_radio.click()

            # Years of experience dropdown/select
            if form_data.get("years_of_experience"):
                await self.logs_manager.debug("Setting years of experience")
                exp_select = await self.dom_service.query_selector('select[id*="experience"]')
                if exp_select:
                    await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN / 1000)
                    await exp_select.select_option(label=form_data["years_of_experience"])

            # A required checkbox may attest to qualifications or consent. Only
            # act on an explicit answer keyed by the field's name or id.
            required_checkboxes = await self.dom_service.query_selector_all(
                'input[type="checkbox"][required]'
            )
            if required_checkboxes:
                await self.logs_manager.debug(f"Processing {len(required_checkboxes)} required checkboxes")
            for checkbox in required_checkboxes:
                if not await checkbox.is_visible():
                    continue
                if not await checkbox.is_checked():
                    key = await checkbox.get_attribute("name") or await checkbox.get_attribute("id")
                    if form_data.get(key) is not True:
                        await self.logs_manager.warning("A required checkbox needs an explicit answer")
                        return False
                    await checkbox.check()

            # Handle any required text areas (e.g., additional information)
            required_textareas = await self.dom_service.query_selector_all(
                'textarea[required]'
            )
            if required_textareas:
                await self.logs_manager.debug(f"Processing {len(required_textareas)} required text areas")
            for textarea in required_textareas:
                if not await textarea.is_visible():
                    continue
                existing_value = await textarea.input_value()
                if not existing_value:
                    key = await textarea.get_attribute("name") or await textarea.get_attribute("id")
                    answer = form_data.get(key)
                    if answer is None or str(answer).strip() == "":
                        await self.logs_manager.warning("A required question needs an explicit answer")
                        return False
                    await textarea.fill(str(answer))

            await self.logs_manager.debug("Completed processing current form step")
            return True

        except Exception as e:
            await self.logs_manager.error(f"Error filling current step fields: {e}")
            return False

    async def _check_disqualifying_questions(self) -> bool:
        """
        Check for any disqualifying questions that might prevent application.
        Returns True if we can continue, False if we should skip.
        """
        try:
            exp_question = await self.dom_service.query_selector('label:has-text("years of experience")')
            if exp_question:
                await self.logs_manager.debug("Found experience requirement question")

            cert_question = await self.dom_service.query_selector('label:has-text("certifications")')
            if cert_question:
                await self.logs_manager.debug("Found certification requirement")

            return True  # Continue by default

        except Exception as e:
            await self.logs_manager.error(f"Error checking disqualifying questions: {e}")
            return False

    # -------------------------------------------------------------------------
    # Internal Form Filling Logic
    # -------------------------------------------------------------------------
    async def _fill_field(
        self,
        field_name: str,
        value: Any,
        selector: str,
        field_type: str,
        required: bool = False
    ):
        """
        Fill a single form field. Dispatches to specialized handlers.

        Args:
            field_name (str): The form_data key.
            value (Any): The value for this field (could be text, a file path, or a dict for cover letter).
            selector (str): CSS selector for the element.
            field_type (str): e.g. "text", "upload", "cover_letter_text", etc.
            required (bool): Whether this field is mandatory.
        """
        await self._human_delay(0.8, 1.5)

        if field_type in ["text", "select", "checkbox", "radio"]:
            element = await self._wait_for_element(selector)
            if field_type == "text":
                await self._handle_text_field(element, value)
            elif field_type == "select":
                await self._handle_select(element, value)
            elif field_type == "checkbox":
                await self._handle_checkbox(element, value)
            elif field_type == "radio":
                await self._handle_radio(selector, value)

        elif field_type == "upload":
            element = await self._wait_for_element(selector)
            await self._handle_file_upload(element, value, required)

        elif field_type in ["cover_letter_text", "cover_letter_upload"]:
            await self._handle_cover_letter(field_type, selector, value, required)
        else:
            raise ValueError(f"Unknown field type '{field_type}' for '{field_name}'")

    # -------------------------------------------------------------------------
    # Handler Methods
    # -------------------------------------------------------------------------
    async def _handle_text_field(self, element, text_value: Union[str, int, float]):
        """Clears existing text and types new text into the field."""
        await element.fill("")
        await self._human_delay(0.4, 0.9)
        await element.type(str(text_value))

    async def _handle_select(self, element, value: Any):
        """Handle <select> dropdown by selecting an option with the given 'value'."""
        await self._human_delay(0.4, 0.9)
        await element.select_option(value=str(value))

    async def _handle_checkbox(self, element, value: bool):
        """If 'value' is True, ensure the checkbox is checked; if False, ensure it's unchecked."""
        if not isinstance(value, bool):
            raise ValueError("Checkbox answers must be booleans")
        current_state = await element.is_checked()
        if bool(value) != current_state:
            await self._human_delay(0.3, 0.8)
            await element.click()

    async def _handle_radio(self, selector_base: str, value: Any):
        """Handle radio button groups like input[name='gender'][value='female']."""
        await self._human_delay(0.3, 0.8)
        radio_selector = f"{selector_base}[value={json.dumps(str(value))}]"
        radio_element = await self._wait_for_element(radio_selector)
        await radio_element.click()

    async def _handle_file_upload(self, element, file_path: str, required: bool):
        """Handle a file upload input (e.g., for CV)."""
        if not file_path or not Path(file_path).is_file():
            msg = f"File to upload not found: {file_path}"
            if required:
                raise FileNotFoundError(msg)
            else:
                await self.logs_manager.warning(f"{msg}, skipping upload.")
                return

        await self._human_delay(0.6, 1.2)
        await element.set_input_files(file_path)

    async def _handle_cover_letter(self, field_type: str, selector: str, value: Any, required: bool):
        """
        Generate or retrieve a cover letter, then either fill or upload it.
        If generation fails, retry once; fail the field if it is required.
        """
        attempts = 0
        cover_text = None

        while attempts < 2 and cover_text is None:
            try:
                await self.logs_manager.info("Attempting to generate cover letter...")
                cover_text = await self._generate_cover_letter_if_needed(value)
            except Exception as e:
                attempts += 1
                await self.logs_manager.error(f"Cover letter generation failed (attempt {attempts}). Error: {e}")
                if attempts < 2:
                    await self.logs_manager.info("Retrying cover letter generation...")
                else:
                    if required:
                        await self.logs_manager.warning("Required cover letter generation failed twice")
                        raise ValueError("Required cover letter could not be generated; supply its text") from e
                    else:
                        await self.logs_manager.warning("Cover letter not required; skipping after failures.")
            else:
                # If we got cover_text successfully, break
                if cover_text:
                    await self.logs_manager.info("Cover letter generated successfully")
                break

        if not cover_text:
            if required:
                raise ValueError("A required cover letter was not provided")
            await self.logs_manager.warning("No cover letter generated or provided. Skipping.")
            return

        if field_type == "cover_letter_text":
            element = await self._wait_for_element(selector)
            await self._handle_text_field(element, cover_text)
            await self.logs_manager.info("Cover letter text filled in form")
        elif field_type == "cover_letter_upload":
            file_path = await self._write_cover_letter_to_file(cover_text)
            try:
                element = await self._wait_for_element(selector)
                await self._handle_file_upload(element, file_path, required=True)
                await self.logs_manager.info("Cover letter uploaded as file")
            finally:
                Path(file_path).unlink(missing_ok=True)

    # -------------------------------------------------------------------------
    # Cover Letter Generation Logic
    # -------------------------------------------------------------------------
    async def _generate_cover_letter_if_needed(self, value: Any) -> str:
        """If 'value' is a string, use it. If it's a dict, call GPT. Otherwise, return empty."""
        if isinstance(value, str):
            await self.logs_manager.debug("Using provided cover letter text")
            return value

        if isinstance(value, dict):
            job_title = value.get("job_title", "N/A")
            job_desc = value.get("job_description", "")
            await self.logs_manager.debug(f"Generating cover letter for position: {job_title}")
            cover_text = await self._call_llm_cover_letter(job_title, job_desc)
            return cover_text

        return ""

    async def _call_llm_cover_letter(self, job_title: str, job_description: str) -> str:
        """Example GPT-4 call, done via run_in_executor for a sync OpenAI call."""
        if not os.getenv("OPENAI_API_KEY"):
            error_msg = "OpenAI API key not set. Please set OPENAI_API_KEY."
            await self.logs_manager.error(error_msg)
            raise ValueError(error_msg)

        prompt = (
            f"Write a concise but effective cover letter for a position:\n"
            f"Job Title: {job_title}\n"
            f"Job Description: {job_description}\n"
            f"Keep it professional, 200 words or fewer."
        )

        try:
            await self.logs_manager.debug("Calling OpenAI API for cover letter generation...")
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, self._sync_openai_chat_completion, prompt)
            await self.logs_manager.debug("Cover letter generated successfully")
            return response
        except Exception as e:
            error_msg = f"OpenAI GPT-4o cover letter generation failed: {str(e)}"
            await self.logs_manager.error(error_msg)
            raise RuntimeError(error_msg)

    def _sync_openai_chat_completion(self, prompt: str) -> str:
        """Blocking call to OpenAI's ChatCompletion API (GPT-4o)."""
        try:
            with openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=30.0, max_retries=1) as client:
                response = client.chat.completions.create(
                    model=self.settings.get("cover_letter_model", "gpt-4o"),
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=0.7
                )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {str(e)}")

    async def _write_cover_letter_to_file(self, cover_text: str) -> str:
        """Write cover letter text to a .txt file for uploading. Returns file path."""
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="cover_letter_", encoding="utf-8", delete=False) as output:
                output.write(cover_text)
                temp_file = Path(output.name)
            await self.logs_manager.debug(f"Cover letter written to temporary file: {temp_file}")
            return str(temp_file)
        except Exception as e:
            error_msg = f"Failed to write cover letter to file: {e}"
            await self.logs_manager.error(error_msg)
            raise RuntimeError(error_msg)

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    async def _wait_for_element(self, selector: str):
        """
        Wait for an element to be visible, returning the element handle.
        Uses DomService internally.
        """
        try:
            await self.logs_manager.debug(f"Waiting for element: {selector}")
            element = await self.dom_service.wait_for_selector(
                selector,
                timeout=TimingConstants.DEFAULT_TIMEOUT
            )
            if element is None:
                raise PlaywrightTimeoutError(f"Element not found: {selector}")
            await self.logs_manager.debug(f"Element found: {selector}")
            return element
        except PlaywrightTimeoutError:
            error_msg = f"Timeout waiting for element: {selector}"
            await self.logs_manager.error(error_msg)
            raise Exception(error_msg)

    async def _human_delay(self, min_sec: float = None, max_sec: float = None):
        """
        Short random delay to mimic human-like interaction.
        Defaults are shorter for a faster user experience
        but still not instantaneous.
        """
        min_sec = min_sec if min_sec is not None else TimingConstants.HUMAN_DELAY_MIN
        max_sec = max_sec if max_sec is not None else TimingConstants.HUMAN_DELAY_MAX
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
