import asyncio
import logging
import os
from dotenv import load_dotenv

# Load environment variables (MISTRAL_API_KEY is needed)
load_dotenv()

from agents.messaging.graph import messaging_graph
from models.resume import MatchedJob

# Set up logging to see the agent's progress
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

async def run_test():
    print("\n" + "="*50)
    print("Testing Messaging Agent with Dummy Data")
    print("="*50 + "\n")

    # 1. Create dummy jobs with recruiter info
    # Job A: With Email
    job_a = MatchedJob(
        content_hash="hash_a",
        title="AI Engineer",
        company="OpenAI",
        location="San Francisco, CA",
        description="We are looking for an AI Engineer to build LLM pipelines.",
        source_url="https://openai.com/jobs/1",
        source_platform="company_site",
        poster_type="direct_hire",
        match_score=0.92,
        skills=["Python", "PyTorch", "LLMs"],
        top_matching_skills=["Python", "LLMs"],
        resume_summary="Experienced AI developer with a focus on LangGraph and Mistral AI.",
        recruiter={
            "name": "Sam Altman",
            "email": "sam@openai.com"
        }
    )

    # Job B: With LinkedIn
    job_b = MatchedJob(
        content_hash="hash_b",
        title="ML Operations Engineer",
        company="Mistral AI",
        location="Paris, France",
        description="Help us scale our open-source models.",
        source_url="https://mistral.ai/jobs/2",
        source_platform="linkedin",
        poster_type="direct_hire",
        match_score=0.88,
        skills=["Kubernetes", "Docker", "Python"],
        top_matching_skills=["Kubernetes", "Python"],
        resume_summary="DevOps enthusiast with experience in ML infrastructure.",
        recruiter={
            "name": "Arthur Mensch",
            "linkedin_url": "https://www.linkedin.com/in/arthurmensch"
        }
    )

    # Job C: No contact info (should be ignored for drafts)
    job_c = MatchedJob(
        content_hash="hash_c",
        title="Python Developer",
        company="GenericCorp",
        location="Remote",
        source_url="https://generic.com/jobs/3",
        source_platform="indeed",
        poster_type="agency_recruiter",
        match_score=0.75,
        description="Python developer needed.",
        recruiter=None
    )

    # 2. Prepare the state
    initial_state = {
        "user_id": "test_user_123",
        "ranked_jobs": [job_a, job_b, job_c],
        "jobs_with_drafts": [],
        "errors": [],
        "status": "starting"
    }

    # 3. Run the messaging graph
    print("Running messaging agent...")
    try:
        final_state = await messaging_graph.ainvoke(initial_state)
        
        results = final_state.get("jobs_with_drafts", [])
        print(f"\n✓ Processed {len(results)} jobs.")
        
        # 4. Check results
        for i, job in enumerate(results):
            print(f"\n--- Job {i+1}: {job.title} @ {job.company} ---")
            if job.outreach_email_draft:
                print(f"📧 EMAIL DRAFT GENERATED:\n{job.outreach_email_draft[:200]}...")
            if job.outreach_linkedin_draft:
                print(f"🔗 LINKEDIN DRAFT GENERATED:\n{job.outreach_linkedin_draft}")
            if not job.outreach_email_draft and not job.outreach_linkedin_draft:
                print("No draft generated (Reason: Missing contact info or error)")
                
    except Exception as e:
        print(f"✗ Agent failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
