import { Router } from 'express';
import {
  getQuestions,
  startAssessment,
  submitResponse,
  completeAssessment,
  getUserAssessments,
} from '../controllers/assessmentController';
import { authenticateToken } from '../middleware/auth';

const router = Router();

router.get('/questions', getQuestions);
router.post('/start', authenticateToken, startAssessment);
router.post('/response', authenticateToken, submitResponse);
router.post('/:assessmentId/complete', authenticateToken, completeAssessment);
router.get('/my-assessments', authenticateToken, getUserAssessments);

export default router;