import sys
import argparse
from dfm.report.runner import analyze_and_generate_report


def main():
    parser = argparse.ArgumentParser(
        prog="report_gen",
        description="DFM Report Generator for Injection Molded Parts (Structured JSON & Engineering PDF)"
    )
    parser.add_argument(
        "pipeline_output_file",
        type=str,
        help="Path to the STEP CAD file (.stp / .step) or raw pipeline output JSON"
    )
    parser.add_argument(
        "--part",
        type=str,
        default=None,
        help="Name of the part (defaults to input filename without extension)"
    )
    parser.add_argument(
        "--texture",
        type=str,
        choices=["plain", "textured", "leather"],
        default="plain",
        help="Surface texture grain for draft angle threshold: plain (1.0°), textured (3.0°), or leather (5.0°)"
    )
    parser.add_argument(
        "--material",
        type=str,
        default="Generic",
        help="Polymer material name (e.g. ABS, PP, Nylon, Polycarbonate, Generic)"
    )
    parser.add_argument(
        "--units",
        type=str,
        default="mm",
        help="Measurement units for report (default: mm)"
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default=None,
        help="Output directory for generated <part>_report.json and <part>_report.pdf (default: current working directory or input directory)"
    )

    args = parser.parse_args()

    try:
        json_out, pdf_out, report_data = analyze_and_generate_report(
            input_path=args.pipeline_output_file,
            part_name=args.part,
            texture=args.texture,
            material=args.material,
            units=args.units,
            outdir=args.outdir
        )
        print("==================================================================")
        print("DFM REPORT GENERATION SUCCESSFUL")
        print("==================================================================")
        print(f"Part Name:       {report_data['part_summary']['part_name']}")
        print(f"Material:        {report_data['part_summary']['material']}")
        print(f"Texture Mode:    {report_data['draft_analysis']['texture_type']} (Threshold >= {report_data['draft_analysis']['threshold_used']} deg)")
        print(f"JSON Report:     {json_out}")
        print(f"PDF Report:      {pdf_out}")
        print("------------------------------------------------------------------")
        print(f"Draft Status:    PASS: {report_data['draft_analysis']['summary']['PASS']}, "
              f"LOW: {report_data['draft_analysis']['summary']['LOW_DRAFT']}, "
              f"ZERO: {report_data['draft_analysis']['summary']['ZERO_DRAFT']}, "
              f"NEGATIVE: {report_data['draft_analysis']['summary']['NEGATIVE_DRAFT']}")
        print(f"Undercuts:       {len(report_data['undercuts'])} detected")
        print(f"Wall Thickness:  Nominal: {report_data['wall_thickness'].get('nominal_thickness', 0)} mm")
        print("==================================================================")
        return 0

    except Exception as e:
        import traceback
        print(f"Error during DFM report generation: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
