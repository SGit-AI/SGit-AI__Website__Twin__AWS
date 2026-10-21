<!-- The brief, published in full and as written: Dinis Cruz's third message of 21 October 2026, a voice
     memo transcribed. Status: accepted, built (site v0.3.0). Never edited; corrections go in
     BRIEF-CORRECTIONS.md. Content CC BY 4.0. -->

# Brief 3: the S3 browser, OSBot-AWS, a Python twin and AWS sessions (21 October 2026)

**From:** Dinis Cruz, a voice memo transcribed · **Status:** accepted and built in site v0.3.0, the Cognito and other sign-in methods measured and not built · **Corrections:** [BRIEF-CORRECTIONS.md](../BRIEF-CORRECTIONS.md)

---

This is great. So can you build a first S3 browser, which basically will simulate S3, that should look just like S3 from Biodite, right? From Python, and see if we can use then Python natively for all our methods, and also can you try OSBot AWS too? Because that already has massive amount of helpers, like you'll see, and basically you can actually see that we use that quite heavily in our other projects. And basically, if OSBot and OSBot utils run in a browser, and I believe they do, we already have a lot of the code base that we built before that we can reuse. So and also the other powerful thing here is that you could then test the codes in both your CI pipeline and on the browser, and the code will be the same, right? In a way. And actually your code on the CI pipeline should also be hitting the twin, and because here's my question, right? If you can run Biodite there, should the twin? Well, the twin, I guess, is the question for you, right? Do you want to build a twin in JavaScript or do you want to build a twin in Python? Because the twin should look like a normal API, because you're simulating the AWS APIs. I think building in Python is better because it means that we keep our code base for backend stuff kind of all in Python, and also it means that we could always run it, and I think some of the experiments I've done before were also done in Python. So yeah, see if you can implement that and do the first MVP of this. And also, can you create a page that details the documentation for how to use AWS, to configure AWS, so that you have that single sign-on mode that allows me to log in and get those temporary session tokens that I can then give. So I need a UI that I can literally just copy and paste that. And let's figure out if there's even a better way of doing that. Maybe using Cognito and stuff like that. But let's add support for those sessions, because I think that's a good way to support it, because that could even be the first one. And then we'll start implementing things like Cognito and other SSO that AWS has to create that very granular permission set. And remember that you have vaults from the browser that you can access. The other thing that you want to take a look at is that if you look at the tools.sgraph.ai and the repo, we already done a huge amount of work there. In fact, we even have a virtual file system that we created that we should be trying to leverage here.

---

Two messages that arrived while this was being built:

> ok I just wired in GitHub pages and created the dev branch, can you you push to dev?

> when finished
