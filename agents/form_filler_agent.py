"""
Form Filling Agent (Async, Playwright) - GPT-4o Cover Letter Integration

Enhancements:
1. Cover letter generation using GPT-4o.
2. Retry logic (once) if cover letter generation fails.
3. If a cover letter is required and both attempts fail, ask user for manual input; 
   otherwise, skip it.
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
from typing import Any, Dict, Union, Optional
from pathlib import Path

import openai
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from constants import TimingConstants, Selectors, Messages
from utils.telemetry import TelemetryManager
from utils.dom.dom_service import DomService

# Ensure your OPENAI_API_KEY or relevant GPT-4 key is in env vars.
openai.api_key = os.getenv("OPENAI_API_KEY", "")

class FormFillerAgent:
    def __init__(
        self,
        dom_service: DomService,
        default_wait: float = 10.0,  # seconds
        raise_on_error: bool = False
    ):
        """
        Args:
            dom_service (DomService): A DomService instance to handle all DOM interactions.
            default_wait (float): Default wait time in seconds for element lookups (unused here, but can be stored if needed).
            raise_on_error (bool): If True, raise exceptions on first error.
                                   If False, log error and continue filling other fields.
        """
        self.dom_service = dom_service
        self.default_wait = default_wait
        self.raise_on_error = raise_on_error

        # Standard delays
        self.human_delay_min = 0.3  # seconds
        self.human_delay_max = 1.0  # seconds
        self.action_delay = 2.0     # seconds (for form submissions)
        self.transition_delay = 3.0 # seconds (for page transitions)
        self.poll_interval = 0.5    # seconds (for condition checks)

        self.telemetry = TelemetryManager()

    async def fill_form(self, form_data: Dict[str, Any], form_mapping: Dict[str, Dict[str, Any]]):
        """
        Fill a form using provided data and field mapping.
        
        If a mapping entry includes {"required": True}, we treat that field as mandatory.
        For example:
          "cover_letter": {"selector": "textarea[name='cover_letter']", "type": "cover_letter_text", "required": True}
        """
        await self.telemetry.track_event(
            "form_filling",
            {"form_type": form_data.type},
            success=True
        )

        for field_name, field_value in form_data.items():
            if field_name not in form_mapping:
                print(f"[FormFillerAgent] No mapping for field '{field_name}', skipping.")
                continue

            config = form_mapping[field_name]
            selector = config["selector"]
            field_type = config.get("type", "text")
            required = config.get("required", False)  # whether the field is mandatory

            try:
                await self._fill_field(field_name, field_value, selector, field_type, required)
                await asyncio.sleep(TimingConstants.FORM_FIELD_DELAY)  # Delay between fields
            except Exception as e:
                error_msg = f"[FormFillerAgent] Error filling field '{field_name}': {str(e)}"
                if self.raise_on_error:
                    raise Exception(error_msg)
                else:
                    print(error_msg)
                    # Log error and continue filling remaining fields

    async def submit_form(self, submit_button_selector: str) -> bool:
        """
        Clicks the submit button, returns True if successful or False if not.

        Raises an exception if not found and raise_on_error=True.
        """
        await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN)  # Delay before submission
        try:
            element = await self._wait_for_element(submit_button_selector)
            await element.click()
            await asyncio.sleep(TimingConstants.FORM_SUBMIT_DELAY)  # Delay after submission
            return True
        except Exception as e:
            error_msg = f"[FormFillerAgent] Could not submit form: {str(e)}"
            if self.raise_on_error:
                raise Exception(error_msg)
            else:
                print(error_msg)
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
            
            # Step 1: Handle CV upload if required
            await self._handle_cv_upload(form_data.get("cv_path"))
            
            # Step 2: Process each form step until submission
            while True:
                # Check for final submit button first
                submit_btn = await self.dom_service.query_selector('button[aria-label="Submit application"]')
                if submit_btn:
                    await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN)
                    await submit_btn.click()
                    await asyncio.sleep(TimingConstants.FORM_SUBMIT_DELAY)
                    return "applied"
                
                # Fill visible form fields on current step
                await self._fill_current_step_fields(form_data)
                
                # Look for and click "Next" button
                next_btn = await self.dom_service.query_selector('button[aria-label="Continue to next step"]')
                if next_btn:
                    await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN)
                    await next_btn.click()
                    await asyncio.sleep(TimingConstants.ACTION_DELAY)
                else:
                    print("[FormFillerAgent] No next or submit button found.")
                    return "failed"
                    
        except Exception as e:
            print(f"[FormFillerAgent] Easy Apply form filling failed: {e}")
            return "failed"

    async def _handle_cv_upload(self, cv_path: Optional[str]):
        """Handle CV upload if required and CV path is provided."""
        try:
            upload_input = await self.dom_service.query_selector('input[type="file"][name="fileId"]')
            if upload_input:
                if cv_path:
                    await upload_input.set_input_files(cv_path)
                    await asyncio.sleep(TimingConstants.FILE_UPLOAD_DELAY)
                else:
                    print("[FormFillerAgent] CV upload required but no CV path provided.")
        except Exception as e:
            print(f"[FormFillerAgent] CV upload failed: {e}")

    async def _fill_current_step_fields(self, form_data: Dict[str, Any]):
        """
        Fill all visible fields in the current step of the Easy Apply form.
        Handles common LinkedIn form field types.
        """
        try:
            # Phone number field
            phone_input = await self.dom_service.query_selector('input[name="phoneNumber"]')
            if phone_input and form_data.get("phone"):
                await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN)
                await phone_input.fill(form_data["phone"])

            # Work authorization radio buttons
            if form_data.get("work_authorization"):
                auth_radio = await self.dom_service.query_selector(
                    f'label:has-text("{form_data["work_authorization"]}")'
                )
                if auth_radio:
                    await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN)
                    await auth_radio.click()

            # Years of experience dropdown/select
            if form_data.get("years_of_experience"):
                exp_select = await self.dom_service.query_selector('select[id*="experience"]')
                if exp_select:
                    await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN)
                    await exp_select.select_option(label=form_data["years_of_experience"])

            # Handle any required checkboxes (e.g., certifications)
            required_checkboxes = await self.dom_service.query_selector_all(
                'input[type="checkbox"][required]'
            )
            for checkbox in required_checkboxes:
                if not await checkbox.is_checked():
                    await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN)
                    await checkbox.click()

            # Handle any required text areas (e.g., additional information)
            required_textareas = await self.dom_service.query_selector_all(
                'textarea[required]'
            )
            for textarea in required_textareas:
                existing_value = await textarea.input_value()
                if not existing_value:
                    await asyncio.sleep(TimingConstants.HUMAN_DELAY_MIN)
                    await textarea.fill("N/A")

        except Exception as e:
            print(f"[FormFillerAgent] Error filling current step fields: {e}")

    async def _check_disqualifying_questions(self) -> bool:
        """
        Check for any disqualifying questions that might prevent application.
        Returns True if we can continue, False if we should skip.
        """
        try:
            exp_question = await self.dom_service.query_selector('label:has-text("years of experience")')
            if exp_question:
                print("[FormFillerAgent] Found experience requirement question")
                
            cert_question = await self.dom_service.query_selector('label:has-text("certifications")')
            if cert_question:
                print("[FormFillerAgent] Found certification requirement")
                
            return True  # Continue by default
            
        except Exception as e:
            print(f"[FormFillerAgent] Error checking disqualifying questions: {e}")
            return True  # Continue on error

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
            print(f"[FormFillerAgent] Unknown field type '{field_type}' for '{field_name}', skipping.")

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
        current_state = await element.is_checked()
        if bool(value) != current_state:
            await self._human_delay(0.3, 0.8)
            await element.click()

    async def _handle_radio(self, selector_base: str, value: Any):
        """Handle radio button groups like input[name='gender'][value='female']."""
        await self._human_delay(0.3, 0.8)
        radio_selector = f"{selector_base}[value='{value}']"
        radio_element = await self._wait_for_element(radio_selector)
        await radio_element.click()

    async def _handle_file_upload(self, element, file_path: str, required: bool):
        """Handle a file upload input (e.g., for CV)."""
        if not file_path or not Path(file_path).exists():
            msg = f"File to upload not found: {file_path}"
            if required:
                new_path = input("Required file not found. Provide a valid file path or press enter to skip: ").strip()
                if new_path and Path(new_path).exists():
                    file_path = new_path
                else:
                    print("[FormFillerAgent] Skipping upload since no valid file was provided.")
                    return
            else:
                print(f"[FormFillerAgent] {msg}, skipping upload.")
                return

        await self._human_delay(0.6, 1.2)
        await element.set_input_files(file_path)

    async def _handle_cover_letter(self, field_type: str, selector: str, value: Any, required: bool):
        """
        Generate or retrieve a cover letter, then either fill or upload it.
        If generation fails, retry once; if still failing and required, prompt user.
        """
        attempts = 0
        cover_text = None

        while attempts < 2 and cover_text is None:
            try:
                cover_text = await self._generate_cover_letter_if_needed(value)
            except Exception as e:
                attempts += 1
                print(f"[FormFillerAgent] Cover letter generation failed (attempt {attempts}). Error: {e}")
                if attempts < 2:
                    print("[FormFillerAgent] Retrying cover letter generation...")
                else:
                    if required:
                        # Prompt user for manual cover letter
                        user_input = input("Cover letter is required but generation failed twice. Please paste cover letter text: ").strip()
                        if user_input:
                            cover_text = user_input
                        else:
                            print("[FormFillerAgent] No cover letter provided; skipping.")
                    else:
                        print("[FormFillerAgent] Cover letter not required; skipping after failures.")
            else:
                # If we got cover_text successfully, break
                break

        if not cover_text:
            print("[FormFillerAgent] No cover letter generated or provided. Skipping.")
            return

        if field_type == "cover_letter_text":
            element = await self._wait_for_element(selector)
            await self._handle_text_field(element, cover_text)
        elif field_type == "cover_letter_upload":
            file_path = await self._write_cover_letter_to_file(cover_text)
            element = await self._wait_for_element(selector)
            await self._handle_file_upload(element, file_path, required=False)
            # Cleanup
            if Path(file_path).exists():
                try:
                    Path(file_path).unlink()
                except:
                    pass

    # -------------------------------------------------------------------------
    # Cover Letter Generation Logic
    # -------------------------------------------------------------------------
    async def _generate_cover_letter_if_needed(self, value: Any) -> str:
        """If 'value' is a string, use it. If it's a dict, call GPT. Otherwise, return empty."""
        if isinstance(value, str):
            return value

        if isinstance(value, dict):
            job_title = value.get("job_title", "N/A")
            job_desc = value.get("job_description", "")
            cover_text = await self._call_llm_cover_letter(job_title, job_desc)
            return cover_text

        return ""

    async def _call_llm_cover_letter(self, job_title: str, job_description: str) -> str:
        """Example GPT-4 call, done via run_in_executor for a sync OpenAI call."""
        prompt = (
            f"Write a concise but effective cover letter for a position:\n"
            f"Job Title: {job_title}\n"
            f"Job Description: {job_description}\n"
            f"Keep it professional, 200 words or fewer."
        )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, self._sync_openai_chat_completion, prompt)
        return response

    def _sync_openai_chat_completion(self, prompt: str) -> str:
        """Blocking call to OpenAI's ChatCompletion API (GPT-4o)."""
        if not openai.api_key:
            raise ValueError("OpenAI API key not set. Please set OPENAI_API_KEY.")

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI GPT-4o cover letter generation failed: {str(e)}")

    async def _write_cover_letter_to_file(self, cover_text: str) -> str:
        """Write cover letter text to a .txt file for uploading. Returns file path."""
        temp_file = Path("temp_cover_letter.txt")
        temp_file.write_text(cover_text, encoding="utf-8")
        return str(temp_file)

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    async def _wait_for_element(self, selector: str):
        """
        Wait for an element to be visible, returning the element handle.
        Uses DomService internally.
        """
        try:
            element = await self.dom_service.wait_for_selector(
                selector,
                timeout=TimingConstants.DEFAULT_TIMEOUT
            )
            return element
        except PlaywrightTimeoutError:
            raise Exception(f"Timeout waiting for element: {selector}")

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
