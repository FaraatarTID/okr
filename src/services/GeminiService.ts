import { GoogleGenerativeAI } from "@google/generative-ai";
import { Node } from "../types";

let genAI: GoogleGenerativeAI | null = null;
let model: any = null;

export const GeminiService = {
    isConfigured: () => !!import.meta.env.VITE_GEMINI_API_KEY,

    evaluateProgress: async (node: Node, allNodes: Record<string, Node>): Promise<{ score: number; analysis: string }> => {
        const apiKey = import.meta.env.VITE_GEMINI_API_KEY;
        if (!apiKey) {
            throw new Error("Gemini API Key is missing. Please configure VITE_GEMINI_API_KEY in .env file.");
        }

        if (!genAI) {
            genAI = new GoogleGenerativeAI(apiKey);
            model = genAI.getGenerativeModel({ model: "gemini-flash-latest" });
        }

        // Collect children details (tasks/initiatives)
        const children = node.children.map(id => allNodes[id]).filter(Boolean);
        
        // Prepare prompt
        const prompt = `
        You are an OKR AI Analyst. Your goal is to evaluate the progress of a Key Result based on its sub-tasks and initiatives.
        
        Key Result: "${node.title}"
        Description: "${node.description || 'N/A'}"
        
        Sub-items:
        ${children.map(child => `- [${child.type.toUpperCase()}] ${child.title} (Time spent: ${child.timeSpent}m, Status: ${child.progress === 100 ? 'DONE' : 'IN PROGRESS'})`).join('\n')}
        
        Instructions:
        1. Analyze the completion status and effort (time spent) of the sub-items.
        2. Assign a progress score from 0 to 100 for the Key Result.
           - If tasks are mostly done, score should be high.
           - If tasks are barely started, score should be low.
           - Consider "Time Spent" as a factor of effort.
        3. Provide a concise justification for the score in Persian (Farsi) language (max 2 sentences).
        
        Output format: JSON
        {
            "score": number,
            "analysis": "string"
        }
        `;

        try {
            const result = await model.generateContent(prompt);
            const response = await result.response;
            const text = response.text();
            
            // Clean up code blocks if present
            const cleanText = text.replace(/```json/g, '').replace(/```/g, '').trim();
            
            const data = JSON.parse(cleanText);
            return {
                score: Math.min(100, Math.max(0, data.score)),
                analysis: data.analysis
            };
        } catch (error) {
            console.error("Gemini analysis failed:", error);
            throw new Error("Failed to analyze progress with Gemini.");
        }
    }
};
