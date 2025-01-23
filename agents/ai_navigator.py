class AINavigator:
    def __init__(self, min_confidence=0.8, max_retries=3):
        self.min_confidence = min_confidence
        self.max_retries = max_retries
        self.retry_count = 0
        
    async def navigate(self, action, context):
        """
        Main navigation method with confidence scoring
        Args:
            action: Navigation action to perform
            context: Contextual information for the action
        Returns:
            Tuple of (success: bool, confidence: float)
        """
        confidence = await self._calculate_confidence(action, context)
        
        if confidence >= self.min_confidence:
            try:
                result = await self._execute_action(action)
                await self._log_success(action, context, confidence)
                return True, confidence
            except Exception as e:
                self.retry_count += 1
                if self.retry_count < self.max_retries:
                    return await self._handle_retry(action, context, confidence, str(e))
                return await self._handle_failure(action, context, confidence, str(e))
        else:
            return await self._handle_low_confidence(action, confidence) 