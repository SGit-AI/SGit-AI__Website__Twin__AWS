<!-- The brief, published in full and as written: Dinis Cruz's seventh message of 21 October 2026 (a voice memo).
     Status: answered in chat; the versioning rule built in site v0.4.1. Never edited; corrections go in
     BRIEF-CORRECTIONS.md. Content CC BY 4.0. -->

# Brief 6: versions, and doing it from the browser (21 October 2026)

**From:** Dinis Cruz · **Status:** answered; the versioning rule built in site v0.4.1; listing buckets through the Cloud Control API proposed, waiting on a check in CloudShell · **Corrections:** [BRIEF-CORRECTIONS.md](../BRIEF-CORRECTIONS.md)

---

Yeah, so from a tag point of view, the workflow that should work is commit to dev, increment a minor version, and commit to main, increment a major version. So, you know, a minor version is v0.3.1 or v0.3.6 and major or v0.4.0 v0.5.0 And all these changes are all minor versions.

Now One thing I'm not understanding is if we're using Boto 3, right, then all these requests are going, you know, via Pydantic, right, through normal HTTP requests, correct? Or you're saying it's the tween that introducing that review? Because we should be, actually, I think you're right, because Boto 3 is hitting our tween, correct? But even then, how is the web server distinguishing a raw HTTP request versus one that we're making from the browser? And then are you saying that the current AWS JS API does not have a list bucket one? Because, by the way, that local relay doesn't work, right? That's not going to be effective. So we need to either have this limitation or we need to find ways around it. Or, sorry, we need to find a way to do it from the browser. So what do you think?
