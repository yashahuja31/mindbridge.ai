import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { AuthRequest } from '../middleware/auth';

const prisma = new PrismaClient();

export const getQuestions = async (req: Request, res: Response) => {
  try {
    const questions = await prisma.question.findMany({
      orderBy: { order: 'asc' },
    });

    res.json(questions);
  } catch (error) {
    console.error('Get questions error:', error);
    res.status(500).json({ error: 'Failed to get questions' });
  }
};

export const startAssessment = async (req: AuthRequest, res: Response) => {
  try {
    const assessment = await prisma.assessment.create({
      data: {
        userId: req.userId!,
        type: 'BIG_FIVE',
        status: 'IN_PROGRESS',
      },
    });

    res.status(201).json(assessment);
  } catch (error) {
    console.error('Start assessment error:', error);
    res.status(500).json({ error: 'Failed to start assessment' });
  }
};

export const submitResponse = async (req: AuthRequest, res: Response) => {
  try {
    const { assessmentId, questionId, value, responseTime } = req.body;

    // Verify assessment belongs to user
    const assessment = await prisma.assessment.findFirst({
      where: {
        id: assessmentId,
        userId: req.userId!,
        status: 'IN_PROGRESS',
      },
    });

    if (!assessment) {
      return res.status(404).json({ error: 'Assessment not found or already completed' });
    }

    // Save response
    const response = await prisma.response.upsert({
      where: {
        assessmentId_questionId: {
          assessmentId,
          questionId,
        },
      },
      update: {
        value,
        responseTime,
      },
      create: {
        assessmentId,
        questionId,
        value,
        responseTime,
      },
    });

    res.json(response);
  } catch (error) {
    console.error('Submit response error:', error);
    res.status(500).json({ error: 'Failed to submit response' });
  }
};

export const completeAssessment = async (req: AuthRequest, res: Response) => {
  try {
    const { assessmentId } = req.params;

    // Get assessment with responses
    const assessment = await prisma.assessment.findFirst({
      where: {
        id: assessmentId,
        userId: req.userId!,
        status: 'IN_PROGRESS',
      },
      include: {
        responses: {
          include: {
            question: true,
          },
        },
      },
    });

    if (!assessment) {
      return res.status(404).json({ error: 'Assessment not found' });
    }

    // Calculate Big Five scores
    const scores = calculateBigFiveScores(assessment.responses);

    // Update assessment as completed
    const updatedAssessment = await prisma.assessment.update({
      where: { id: assessmentId },
      data: {
        status: 'COMPLETED',
        completedAt: new Date(),
        results: scores,
      },
    });

    res.json({
      assessment: updatedAssessment,
      scores,
    });
  } catch (error) {
    console.error('Complete assessment error:', error);
    res.status(500).json({ error: 'Failed to complete assessment' });
  }
};

function calculateBigFiveScores(responses: any[]) {
  const categories = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism'];
  const scores: Record<string, number> = {};

  categories.forEach(category => {
    const categoryResponses = responses.filter(r => r.question.category === category);
    if (categoryResponses.length === 0) {
      scores[category] = 0;
      return;
    }

    let total = 0;
    categoryResponses.forEach(response => {
      let value = response.value;
      // Reverse scoring for reverse questions
      if (response.question.reverse) {
        value = 6 - value; // Convert 1-5 scale: 1->5, 2->4, 3->3, 4->2, 5->1
      }
      total += value;
    });

    // Normalize to 0-1 scale
    const maxPossible = categoryResponses.length * 5;
    const minPossible = categoryResponses.length * 1;
    scores[category] = (total - minPossible) / (maxPossible - minPossible);
  });

  return scores;
}

export const getUserAssessments = async (req: AuthRequest, res: Response) => {
  try {
    const assessments = await prisma.assessment.findMany({
      where: { userId: req.userId! },
      orderBy: { createdAt: 'desc' },
    });

    res.json(assessments);
  } catch (error) {
    console.error('Get assessments error:', error);
    res.status(500).json({ error: 'Failed to get assessments' });
  }
};