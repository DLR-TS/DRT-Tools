# Postprocessing

This is a script for post processing of SUMO output files like tripinfo and dispatchinfo files.

It expects a SUMO simulation with taxi devices. Unfinished tips are filtered.
After processing the output files, a simple excel file is created with a selection of KPI.


## Installation

Install required python packages with:

	pip install -r requirements.txt

## Usage

In your python command prompt, navigate to the folder with postprocessing.py and run:

    python postprocessing.py -t tripinfo.output.xml -o output.xls

Where `tripinfo.output.xml` is the tripinfo output file from your SUMO simulation
and `output.xls` is the file where the post-processing results are written to.
You can use relative or absolute file paths here, e. g. `-d d:/example/tripinfo_example.output.xml`

If you have a dispatchinfo output file, you can include it with:

    python postprocessing.py -t tripinfo.output.xml -d dispatchinfo.output.xml -o output.xls

For further help on the command line arguments run:

    python postprocessing.py --help