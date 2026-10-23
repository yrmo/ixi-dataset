export FREESURFER_HOME=/usr/local/freesurfer/8.2.0
source $FREESURFER_HOME/SetUpFreeSurfer.sh
export SUBJECTS_DIR=$HOME/freesurfer_subjects
mkdir -p $SUBJECTS_DIR

echo $SUBJECTS_DIR

recon-all -i IXI169-Guys-0842-T1.nii -s IXI169 -all
