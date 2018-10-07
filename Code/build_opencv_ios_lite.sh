# Define text colors
red=`tput setaf 1`
green=`tput setaf 2`
yellow=`tput setaf 3`
blue=`tput setaf 4`
magenta=`tput setaf 5`
nocolor=`tput sgr0`

echo -e "Welcome to ${green}OpenCV-iOS-Lite${nocolor} build script 🙂\n"

opencv_sources_folder=""
echo -e "Do you have a local copy of ${magenta}OpenCV${nocolor} sources from ${yellow}GitHub${nocolor}? [y/n] 🤔"
read source_code
case "$source_code" in
  [yY][eE][sS]|[yY])
  printf "\n"
  echo "Please enter the path to ${magenta}OpenCV${nocolor} ${yellow}sources folder${nocolor}. [For example '${green}../opencv${nocolor}']"
  read sources_folder
  opencv_sources_folder=$sources_folder
  ;;
  *)
  printf "\n"
  echo "OK, let's download the source code from ${yellow}GitHub${nocolor}. Please enter the path to ${yellow}save-to directory${nocolor}. [For example '${green}opencv_sources/${nocolor}']"
  read download_folder
  # Refresh download folder
  sudo rm -rf $download_folder
  mkdir $download_folder
  # Clone sources from GitHub
  git clone https://github.com/opencv/opencv.git $download_folder
  echo "Successfully downloaded  ${magenta}OpenCV${nocolor} sources from ${yellow}GitHub${nocolor} to ${green}$download_folder${nocolor} 👌"
  opencv_sources_folder=$download_folder
  ;;
esac

printf "\n"
echo -e "Please, enter the path to the temporary build folder. [For example '${green}build_folder/${nocolor}']"
read build_folder
# Refresh build folder
sudo rm -rf $build_folder
mkdir $build_folder

# Begin to construct arguments for Python script
python_command="sudo python setup_opencv_cmake_build.py $build_folder --opencv $opencv_sources_folder "

printf "\n"
echo "${magenta}OpenCV${nocolor} has the following optional modules: ${yellow}imgcodecs, imgproc, calib3d, features2D, flann, highgui, ml, objdetect, photo, stitching, video, videoio, videostab${nocolor}."
printf "\n"
echo "Please, enter the names of the modules you'd like to include. [For example: '${green}imgproc calib3d flann${nocolor}' ]"
read array_of_modules_to_include

# Create an array containig selected modules with their dependencies
array_of_requred_modules=()
for module in $array_of_modules_to_include
do
  case $module in
    imgcodecs)
    array_of_requred_modules+=('imgcodecs' 'imgproc')
    ;;
    imgproc)
    array_of_requred_modules+=('imgproc')
    ;;
    calib3d)
    array_of_requred_modules+=('calib3d' 'imgproc' 'features2d' 'flann')
    ;;
    features2D)
    array_of_requred_modules+=('features2D' 'imgproc')
    ;;
    flann)
    array_of_requred_modules+=('flann')
    ;;
    highgui)
    array_of_requred_modules+=('highgui' 'imgproc' 'imgcodecs')
    ;;
    ml)
    array_of_requred_modules+=('ml')
    ;;
    photo)
    array_of_requred_modules+=('photo' 'imgproc')
    ;;
    objdetect)
    array_of_requred_modules+=('objdetect' 'imgproc')
    ;;
    stitching)
    array_of_requred_modules+=('stitching' 'imgproc' 'features2d' 'calib3d' 'flann')
    ;;
    video)
    array_of_requred_modules+=('video' 'imgproc')
    ;;
    videoio)
    array_of_requred_modules+=('videoio' 'imgproc' 'imgcodecs')
    ;;
    videostab)
    array_of_requred_modules+=('videostab' 'imgproc' 'features2d' 'video' 'photo' 'calib3d' 'flann')
    ;;
    *)
    printf "\n"
    echo "You've made a mistake in a module name ${red}$module${nocolor} 😕"
    ;;
  esac
done
# Filter for duplication
array_of_requred_modules=($(tr ' ' '\n' <<< "${array_of_requred_modules[@]}" | sort -u | tr '\n' ' '))
printf "\n"
echo "Generating a list of modules you selected + requred dependencies..."
echo "List of modules to include: ${green}'${array_of_requred_modules[@]}'${nocolor}."

# Create a full list of modules to exclude
array_of_modules_to_exclude=('gpu' 'contrib' 'highgui' 'legacy' 'ml' 'nonfree' 'objdetect' 'photo' 'stitching' 'video' 'videoio'  'videostab')
# Filter for requred modules
for module in "${array_of_requred_modules[@]}"
do
  array_of_modules_to_exclude=(${array_of_modules_to_exclude[@]//*$module*})
done
echo "List of modules to exclude: ${red}'${array_of_modules_to_exclude[@]}'${nocolor}."
for module in "${array_of_modules_to_exclude[@]}"
do
  python_command+="--without $module "
done

printf "\n"
echo "You are able to build a multiple architecture fat library. Please, choose the names of the architectures [${yellow}armv7 armv7s arm64 i386 x86_64${nocolor}] you'd like to include. [For example: '${green}arm64 x86_64${nocolor}'. Type '${green}all${nocolor}' to include all the archs.]"
read array_of_archs_to_include
for arch in $array_of_archs_to_include
do
  case $arch in
    armv7)
    python_command+="--armv7-arch "
    ;;
    armv7s)
    python_command+="--armv7s-arch "
    ;;
    arm64)
    python_command+="--arm64-arch "
    ;;
    i386)
    python_command+="--i386-arch "
    ;;
    x86_64)
    python_command+="--x86_64-arch "
    ;;
    all)
    python_command+="--armv7-arch --armv7s-arch --arm64-arch --i386-arch --x86_64-arch "
    ;;
    *)
    printf "\n"
    echo "You've made a mistake in arch name ${red}$arch${nocolor} 😕"
    ;;
  esac
done

printf "\n"
echo "Would you like to build a dynamic framework? [y/n] 🤔"
read dynamic
case "$dynamic" in
  [yY][eE][sS]|[yY])
  python_command+="--dynamic"
  printf "\n"
  echo "Ok, you'll get ${green}dynamic${nocolor} framework 👌"
  ;;
  *)
  printf "\n"
  echo "Ok, you'll get ${green}statically-linked${nocolor} framework 👌"
  ;;
esac

# Execute the constructed python command
$python_command

printf "\n"
echo "Congratulations 🎉🎉🎉"
echo "Opening result..."
open $build_folder/
