The goal of this project is to replicate https://www.nytimes.com/interactive/2023/12/30/opinion/new-york-housing-solution.html 
in San Francisco. The above article was produced by Practice for Architecture and Urbanism (PAU), led by Vishaan Chakrabarti.
See more here https://pau.studio/what/affordable-new-york/


There's going to be multiple parts of this 

1. Create a critera for possible places to upzone. What comes to top of mind is places like parking lots or single floor structures or abandoned buildings. Then, we'll need to make sure they have some proximity to public transportation. Ideally, all potential candidates should be 45 minutes away from say downtown via public transportation. This should be an adjustable knob so we should be able to build heatmaps of all areas 45 minutes away, and 50 minutes away, and 60 minutes away etc. You'll need to think more about optimal critera.
2. Pull the zoning data for SF and find all possible locations. For all the intermediary scripts that are used and made we should check them in at `scripts`. All steps should be reproducible. For pulling zoning data, there's a key provided in `.env.secrets`.
3. Filter all possible candidates to best candidates using our critera from 1. Once again this should be reproducible and something we can work with later.
4. Construct an economic model. I think that based on cities like Austin where increasing housing by x units has lowered the cost by y gives us an example of how to model supply and demand and it's impacts on rental prices. I'd like to be able to say something akin to, if we build x houses in san francisco we can bring down average rent by y. 

The below point should be ignored, we'll handle it later. 
<!-- 3. Using svelte (or solid JS, your choice but I think I slightly prefer svelte) build a site to explore all this data. The site should be viewable almost like a conference website. Ideally this website eventually gets published in an online news article. Text should be single column and there should be ma -->
