import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

const bigFiveQuestions = [
  // Openness to Experience
  { category: 'openness', text: 'I have a vivid imagination.', order: 1, reverse: false },
  { category: 'openness', text: 'I have difficulty understanding abstract ideas.', order: 2, reverse: true },
  { category: 'openness', text: 'I have excellent ideas.', order: 3, reverse: false },
  { category: 'openness', text: 'I am not interested in abstract ideas.', order: 4, reverse: true },
  { category: 'openness', text: 'I have a rich vocabulary.', order: 5, reverse: false },

  // Conscientiousness
  { category: 'conscientiousness', text: 'I am always prepared.', order: 6, reverse: false },
  { category: 'conscientiousness', text: 'I leave my belongings around.', order: 7, reverse: true },
  { category: 'conscientiousness', text: 'I pay attention to details.', order: 8, reverse: false },
  { category: 'conscientiousness', text: 'I make a mess of things.', order: 9, reverse: true },
  { category: 'conscientiousness', text: 'I get chores done right away.', order: 10, reverse: false },

  // Extraversion
  { category: 'extraversion', text: 'I am the life of the party.', order: 11, reverse: false },
  { category: 'extraversion', text: 'I don\'t talk a lot.', order: 12, reverse: true },
  { category: 'extraversion', text: 'I feel comfortable around people.', order: 13, reverse: false },
  { category: 'extraversion', text: 'I keep in the background.', order: 14, reverse: true },
  { category: 'extraversion', text: 'I start conversations.', order: 15, reverse: false },

  // Agreeableness
  { category: 'agreeableness', text: 'I feel others\' emotions.', order: 16, reverse: false },
  { category: 'agreeableness', text: 'I am not really interested in others.', order: 17, reverse: true },
  { category: 'agreeableness', text: 'I take time out for others.', order: 18, reverse: false },
  { category: 'agreeableness', text: 'I insult people.', order: 19, reverse: true },
  { category: 'agreeableness', text: 'I sympathize with others\' feelings.', order: 20, reverse: false },

  // Neuroticism
  { category: 'neuroticism', text: 'I get stressed out easily.', order: 21, reverse: false },
  { category: 'neuroticism', text: 'I am relaxed most of the time.', order: 22, reverse: true },
  { category: 'neuroticism', text: 'I worry about things.', order: 23, reverse: false },
  { category: 'neuroticism', text: 'I seldom feel blue.', order: 24, reverse: true },
  { category: 'neuroticism', text: 'I am easily disturbed.', order: 25, reverse: false },
];

async function main() {
  console.log('🌱 Seeding database...');

  // Create questions
  for (const question of bigFiveQuestions) {
    await prisma.question.create({
      data: question,
    });
  }

  // Create a sample company
  const company = await prisma.company.create({
    data: {
      name: 'TechCorp Inc.',
      industry: 'Technology',
      size: 'medium',
      description: 'A leading technology company focused on innovation.',
      website: 'https://techcorp.com',
      culture: {
        innovation: 0.9,
        collaboration: 0.8,
        flexibility: 0.7,
        growth: 0.9,
      },
    },
  });

  // Create a sample job
  await prisma.job.create({
    data: {
      companyId: company.id,
      title: 'Frontend Developer',
      description: 'Build amazing user experiences with React and TypeScript.',
      requirements: {
        skills: ['React', 'TypeScript', 'CSS', 'JavaScript'],
        experience: 'mid-level',
        personality: {
          openness: 0.7,
          conscientiousness: 0.8,
          extraversion: 0.6,
          agreeableness: 0.7,
          neuroticism: 0.3,
        },
      },
      salaryMin: 70000,
      salaryMax: 90000,
      workStyle: 'hybrid',
    },
  });

  console.log('✅ Database seeded successfully!');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });