import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const deals = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/deals" }),
  schema: z.object({
    title: z.string(),
    category: z.enum(['wellness', 'tech', 'deals']),
    excerpt: z.string(),
    featured: z.boolean().default(false),
    readTime: z.string(),
    publishedAt: z.string(),
  }),
});

export const collections = { deals };
