export interface QuickPrompt {
  label: string;
  query: string;
}

export const QUICK_PROMPTS: QuickPrompt[] = [
  { label: "Revenue this month",    query: "What was my total revenue this month?" },
  { label: "ROAS last 7 days",      query: "What is my ROAS for the last 7 days?" },
  { label: "Top campaigns",         query: "Which ad campaigns had the highest spend last week?" },
  { label: "Orders vs last week",   query: "How did my orders this week compare to last week?" },
  { label: "Shipping cost",         query: "What is my total shipping cost this month?" },
  { label: "RTO rate",              query: "How many orders were returned to origin this month?" },
];
