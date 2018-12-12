Advent of Helga
---------------

That's right, we're improving helga, either core or plugins, for Advent 2018.

Dec 2nd-4th was spent doing other stuff cause i haven't thought of this yet.

Dec 5th: add the ability for
    [helga-alkafact](https://github.com/bigjust/helga-alkafact) to
    pull a random fact from the DB, not requiring an argument.

Dec 9th: starting to get the hang of this daily exercise thing! fixed
    a long-standing annoyance in
    [helga-mimic](https://github.com/bigjust/helga-mimic) where she would
    generate a mimic reply even if the message was a command, thus producing two
    confusing outputs. [issue](https://github.com/bigjust/helga-mimic/issues/3)

Dec 10th: i rediscovered Kerbal Space Program, fuck you

Dec 11th: brainstorming sessions mostly. Research a bug in britcoin's
    balances output, which i think is due to flood limits, so I've decided
    to convert that to a dpaste output. I've decided to try to learn
    Terraform and build a scalable infrastructure for Helga. It'll be
    simple at first, since she doesn't really need to scale, but i
    have some plugin ideas, especially around the `mimic` plugin that
    might require some CPU bursts, especially around training. Also,
    we're going to make a discord backend! I'm anxious to use the tts
    capability as well as the audio streaming, i think some really
    cool shit could come out of that.
